#!/usr/bin/env python3
"""
add_mtn_momo_payments.py
  - Creates a MomoTransaction model to track payment requests.
  - Creates a service class to interact with the MTN MoMo API.
  - Adds endpoints for Request to Pay, Status Polling, and Callback.
  - Updates Billing Dashboard with a "Pay with MoMo" flow.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Install requests ──────────────────────────────────────
print("==> Installing requests")
subprocess.run([str(PY), "-m", "pip", "install", "--quiet", "requests"], check=True)
req_path = ROOT / "requirements.txt"
reqs = req_path.read_text(encoding="utf-8")
if "requests" not in reqs:
    req_path.write_text(reqs.strip() + "\nrequests>=2.31\n", encoding="utf-8")

# ─── 2. BACKEND: Add MomoTransaction Model ─────────────────────────────
print("==> Creating billing/momo_models.py")
write("billing/momo_models.py", '''\
from django.db import models
from common.models import TenantAwareModel

class MomoTransaction(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESSFUL = "SUCCESSFUL", "Successful"
        FAILED = "FAILED", "Failed"

    invoice = models.ForeignKey("billing.Invoice", on_delete=models.CASCADE, related_name="momo_transactions")
    reference_id = models.CharField(max_length=64, unique=True, help_text="MTN X-Reference-Id")
    phone_number = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    external_id = models.CharField(max_length=64, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MoMo {self.reference_id} - {self.status}"
''')

# Add to models.py (import for Django to discover)
bp = ROOT / "billing" / "models.py"
b = bp.read_text(encoding="utf-8")
if "from .momo_models import MomoTransaction" not in b:
    b += "\n\nfrom .momo_models import MomoTransaction\n"
    bp.write_text(b, encoding="utf-8")

# ─── 3. BACKEND: Create MTN Service ────────────────────────────────────
print("==> Creating billing/mtn_service.py")
write("billing/mtn_service.py", '''\
import base64
import uuid
import requests
from decimal import Decimal
from django.utils import timezone
from tenants.models import MobileMoneyConfig

class MTNMoMoService:
    def __init__(self, config: MobileMoneyConfig):
        self.config = config
        self.env = "sandbox" if config.environment == "sandbox" else "mtnzambia"
        self.base_url = f"https://{self.env}.momodeveloper.mtn.com" if self.env == "sandbox" else "https://proxy.momoapi.mtn.com"

    def _get_token(self):
        """OAuth 2.0 Handshake"""
        url = f"{self.base_url}/collection/token/"
        credentials = f"{self.config.api_user}:{self.config.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded}",
            "Ocp-Apim-Subscription-Key": self.config.subscription_key,
        }
        
        r = requests.post(url, headers=headers, timeout=15)
        if r.status_code != 200:
            raise Exception(f"Failed to get token: {r.text}")
        
        return r.json()["access_token"]

    def request_to_pay(self, amount, phone, reference_id, external_id, payer_message):
        """Initiates an async Request to Pay."""
        token = self._get_token()
        url = f"{self.base_url}/collection/v1_0/requesttopay"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": self.env,
            "Ocp-Apim-Subscription-Key": self.config.subscription_key,
            "Content-Type": "application/json",
        }
        
        # Note: For sandbox EUR is used, for Zambia ZMW. 
        currency = "EUR" if self.env == "sandbox" else "ZMW"
        
        payload = {
            "amount": str(amount),
            "currency": currency,
            "externalId": external_id,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone
            },
            "payerMessage": payer_message,
            "payeeNote": "Payment to Nimbus OPD"
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        
        # 202 Accepted means the request was successfully queued
        if r.status_code != 202:
            raise Exception(f"Request failed: {r.text}")
        
        return True

    def check_status(self, reference_id):
        """Polls the status of the transaction."""
        token = self._get_token()
        url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": self.env,
            "Ocp-Apim-Subscription-Key": self.config.subscription_key,
        }
        
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            raise Exception(f"Status check failed: {r.text}")
            
        return r.json()["status"]
''')

# ─── 4. BACKEND: Create the API endpoints ──────────────────────────────
print("==> Creating api/momo_payment_views.py")
write("api/momo_payment_views.py", '''\
import uuid
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from billing.models import Invoice, Payment
from billing.momo_models import MomoTransaction
from billing.mtn_service import MTNMoMoService
from tenants.models import MobileMoneyConfig
from api.permissions import require_roles

class MomoRequestToPayView(APIView):
    permission_classes = [require_roles("admin", "receptionist")]
    
    def post(self, request):
        invoice_id = request.data.get("invoice_id")
        phone = request.data.get("phone_number")
        config_id = request.data.get("config_id")
        
        if not all([invoice_id, phone, config_id]):
            return Response({"detail": "Missing fields"}, status=400)
            
        invoice = Invoice.all_objects.filter(id=invoice_id).first()
        config = MobileMoneyConfig.all_objects.filter(id=config_id).first()
        
        if not invoice or not config:
            return Response({"detail": "Invoice or config not found"}, status=404)
            
        ref_id = str(uuid.uuid4())
        amount = invoice.balance
        
        try:
            service = MTNMoMoService(config)
            service.request_to_pay(
                amount=amount,
                phone=phone,
                reference_id=ref_id,
                external_id=invoice.invoice_no,
                payer_message=f"Payment for {invoice.invoice_no}"
            )
            
            txn = MomoTransaction.objects.create(
                tenant=request.user.tenant,
                invoice=invoice,
                reference_id=ref_id,
                phone_number=phone,
                amount=amount,
                status=MomoTransaction.Status.PENDING,
                external_id=invoice.invoice_no
            )
            
            return Response({"detail": "Request sent to phone", "reference_id": ref_id}, status=202)
            
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class MomoStatusCheckView(APIView):
    permission_classes = [require_roles("admin", "receptionist")]
    
    def get(self, request, reference_id):
        txn = MomoTransaction.all_objects.filter(reference_id=reference_id).first()
        if not txn:
            return Response({"detail": "Transaction not found"}, status=404)
            
        config = MobileMoneyConfig.all_objects.filter(tenant=txn.tenant, provider="mtn_momo").first()
        if not config:
            return Response({"detail": "MoMo config missing"}, status=404)
            
        try:
            service = MTNMoMoService(config)
            new_status = service.check_status(reference_id)
            
            if new_status == "SUCCESSFUL" and txn.status != "SUCCESSFUL":
                txn.status = MomoTransaction.Status.SUCCESSFUL
                txn.save()
                # Auto-create the payment record in the billing system
                Payment.objects.create(
                    invoice=txn.invoice,
                    amount=txn.amount,
                    method=Payment.Method.MOBILE_MONEY,
                    reference=reference_id,
                    received_by=request.user,
                    notes="MTN MoMo Auto-Payment"
                )
            elif new_status == "FAILED":
                txn.status = MomoTransaction.Status.FAILED
                txn.save()
                
            return Response({"status": new_status})
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class MomoCallbackView(APIView):
    """MTN sends a POST here when the payment finishes."""
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        ref_id = request.data.get("referenceId")
        status_str = request.data.get("status")
        
        if not ref_id:
            return Response({"detail": "No referenceId"}, status=400)
            
        txn = MomoTransaction.all_objects.filter(reference_id=ref_id).first()
        if not txn:
            return Response({"detail": "Txn not found"}, status=404)
            
        txn.status = status_str
        if status_str == "FAILED":
            txn.failure_reason = request.data.get("reason", "")
        txn.save()
        
        if status_str == "SUCCESSFUL":
            Payment.objects.create(
                invoice=txn.invoice,
                amount=txn.amount,
                method=Payment.Method.MOBILE_MONEY,
                reference=ref_id,
                received_by=txn.invoice.patient.created_by if hasattr(txn.invoice.patient, 'created_by') else None,
                notes="MTN MoMo Callback Auto-Payment"
            )
            
        return Response({"status": "ok"}, status=200)
''')

# ─── 5. BACKEND: Wire URLs & Migrate ───────────────────────────────────
print("==> Patching api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "MomoRequestToPayView" not in u:
    u = u.replace(
        "from .accounting_views import JournalEntryViewSet",
        "from .accounting_views import JournalEntryViewSet\n"
        "from .momo_payment_views import MomoRequestToPayView, MomoStatusCheckView, MomoCallbackView"
    )
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('momo/request/', MomoRequestToPayView.as_view(), name='momo-request'),\n"
        "    path('momo/status/<str:reference_id>/', MomoStatusCheckView.as_view(), name='momo-status'),\n"
        "    path('momo/callback/', MomoCallbackView.as_view(), name='momo-callback'),"
    )
    up.write_text(u, encoding="utf-8")

print("==> Running migrations")
sh(PY, "manage.py", "makemigrations", "billing")
sh(PY, "manage.py", "migrate")

# ─── 6. FRONTEND: Update Billing Dashboard ─────────────────────────────
print("==> Patching BillingDashboard.tsx")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

# We will add the MoMo Modal logic
if "const [momoInvoice" not in b:
    b = b.replace(
        "const [selectedVisit, setSelectedVisit] = useState<number | null>(null);",
        "const [selectedVisit, setSelectedVisit] = useState<number | null>(null);\n"
        "  const [momoInvoice, setMomoInvoice] = useState<number | null>(null);\n"
        "  const [momoRef, setMomoRef] = useState<string | null>(null);\n"
        "  const [momoPolling, setMomoPolling] = useState(false);\n"
        "  const [momoPhone, setMomoPhone] = useState('');"
    )

    # Add the mutation
    b = b.replace(
        "  const recordPayment = useMutation({",
        '''  const requestMomo = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post("/momo/request/", payload);
      return data;
    },
    onSuccess: (data) => {
      setMomoRef(data.reference_id);
      setMomoPolling(true);
      // Start polling every 3 seconds
      const interval = setInterval(async () => {
        try {
          const { data: statusData } = await api.get(`/momo/status/${data.reference_id}/`);
          if (statusData.status === "SUCCESSFUL") {
            clearInterval(interval);
            setMomoPolling(false);
            setMomoInvoice(null);
            qc.invalidateQueries({ queryKey: ["invoice"] });
            qc.invalidateQueries({ queryKey: ["billing-visits"] });
            alert("Payment Successful!");
          } else if (statusData.status === "FAILED") {
            clearInterval(interval);
            setMomoPolling(false);
            alert("Payment Failed.");
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 3000);
    }
  });

  const recordPayment = useMutation({'''
    )

    # Add the UI button and modal
    old_payment_form = '''                  <button type="submit" disabled={recordPayment.isPending} className="w-full bg-emerald-600 text-white py-2 rounded text-sm font-medium hover:bg-emerald-700">
                    {recordPayment.isPending ? "Processing..." : "Complete Payment"}
                  </button>'''
    
    new_payment_form = '''                  <button type="submit" disabled={recordPayment.isPending} className="w-full bg-emerald-600 text-white py-2 rounded text-sm font-medium hover:bg-emerald-700">
                    {recordPayment.isPending ? "Processing..." : "Complete Cash/Card Payment"}
                  </button>
                  
                  <div className="relative flex py-2 items-center">
                    <div className="flex-grow border-t border-slate-200"></div>
                    <span className="flex-shrink-0 mx-4 text-slate-400 text-xs uppercase font-medium">Or</span>
                    <div className="flex-grow border-t border-slate-200"></div>
                  </div>

                  <button 
                    type="button" 
                    onClick={() => setMomoInvoice(invoice.data.id)}
                    className="w-full bg-amber-400 text-amber-900 py-2 rounded text-sm font-bold hover:bg-amber-500"
                  >
                    Request MTN MoMo Payment
                  </button>'''

    if old_payment_form in b:
        b = b.replace(old_payment_form, new_payment_form)

    # Add the Modal at the very bottom of the component return
    b = b.replace(
        "      </div>\n    </div>\n  );\n}",
        '''      </div>

      {momoInvoice && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white p-6 rounded-xl shadow-xl w-full max-w-sm">
            <h3 className="text-lg font-bold mb-4">MTN MoMo Payment</h3>
            {!momoRef ? (
              <form onSubmit={(e) => {
                e.preventDefault();
                requestMomo.mutate({ invoice_id: momoInvoice, phone_number: momoPhone, config_id: 1 }); // Using config_id 1 for demo
              }}>
                <label className="block text-sm mb-4">
                  <span className="text-slate-600">Customer Phone Number</span>
                  <input value={momoPhone} onChange={e => setMomoPhone(e.target.value)} required placeholder="260966123456" className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <div className="flex justify-end gap-2">
                  <button type="button" onClick={() => setMomoInvoice(null)} className="px-4 py-2 text-slate-600">Cancel</button>
                  <button type="submit" disabled={requestMomo.isPending} className="px-4 py-2 bg-amber-500 text-white rounded font-bold">Send Request</button>
                </div>
              </form>
            ) : (
              <div className="text-center py-4">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-500 mx-auto mb-4"></div>
                <p className="text-slate-600">Waiting for customer to approve on their phone...</p>
                <p className="text-xs text-slate-400 mt-2">Ref: {momoRef}</p>
                <button onClick={() => { setMomoInvoice(null); setMomoRef(null); setMomoPolling(false); }} className="mt-6 text-slate-500 underline">Cancel</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}'''
    )

    bp.write_text(b, encoding="utf-8")

# ─── 7. Build & Push ───────────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(momo): implement actual MTN Request to Pay flow with polling", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")