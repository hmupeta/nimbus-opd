#!/usr/bin/env python3
"""
fix_momo_request_api.py
  - Fixes the `all_objects` crash in the MTN Momo request/status views.
  - Updates BillingDashboard to dynamically fetch the active MoMo config.
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

# ─── 1. BACKEND: Fix the all_objects crash ─────────────────────────────
print("==> Patching api/momo_payment_views.py")
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
        # MobileMoneyConfig uses a standard manager (objects), not all_objects
        config = MobileMoneyConfig.objects.filter(id=config_id).first()
        
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
            
        config = MobileMoneyConfig.objects.filter(tenant=txn.tenant, provider="mtn_momo").first()
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

# ─── 2. FRONTEND: Dynamic config selection ─────────────────────────────
print("==> Updating BillingDashboard.tsx to dynamically select config")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

# Add MoMo configs query
if "momoConfigs = useQuery" not in b:
    b = b.replace(
        'const visits = useQuery({',
        '''const momoConfigs = useQuery({
    queryKey: ["momo-configs-active"],
    queryFn: async () => (await api.get<Paginated<any>>("/mobile-money-configs/")).data.results.filter((c: any) => c.is_active),
  });

  const visits = useQuery({'''
    )

# Update the modal submission to use the dynamic config ID
old_submit = '''              <form onSubmit={(e) => {
                e.preventDefault();
                requestMomo.mutate({ 
                  invoice_id: momoInvoice, 
                  phone_number: momoPhone, 
                  config_id: 1 // Using the first active MoMo config
                });
              }}>'''

new_submit = '''              <form onSubmit={(e) => {
                e.preventDefault();
                const activeConfig = momoConfigs.data?.[0];
                if (!activeConfig) {
                  alert("No active Mobile Money configuration found. Please ask your Finance Manager to set one up.");
                  return;
                }
                requestMomo.mutate({ 
                  invoice_id: momoInvoice, 
                  phone_number: momoPhone, 
                  config_id: activeConfig.id
                });
              }}>'''

if old_submit in b:
    b = b.replace(old_submit, new_submit)
    bp.write_text(b, encoding="utf-8")
    print("   patched BillingDashboard with dynamic config")
else:
    print("   [WARN] Could not find the MoMo form submit logic")

# ─── 3. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "fix(momo): resolve all_objects crash and dynamic config selection", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")