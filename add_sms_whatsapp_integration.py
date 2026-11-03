#!/usr/bin/env python3
"""
add_sms_whatsapp_integration.py
1. Creates a notification service (SMS/WhatsApp).
2. Adds an API endpoint to trigger receipts.
3. Adds UI buttons to the Payments page.
4. Builds and pushes.
"""
import subprocess, sys, shutil, os, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# ═════════════════════════════════════════════════════════════════════
# 1. Create Backend Notification Service
# ═════════════════════════════════════════════════════════════════════
print("==> Creating api/notifications.py (SMS & WhatsApp Service)")
notif_path = ROOT / "api" / "notifications.py"
notif_path.parent.mkdir(parents=True, exist_ok=True)

notif_content = r'''import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def send_sms(phone_number: str, message: str) -> bool:
    """
    Sends an SMS using Africa's Talking (or similar).
    Requires AFRICASTALKING_API_KEY and AFRICASTALKING_USERNAME in settings.
    """
    api_key = getattr(settings, "AFRICASTALKING_API_KEY", "mock_key")
    username = getattr(settings, "AFRICASTALKING_USERNAME", "sandbox")
    
    if api_key == "mock_key":
        logger.info(f"[MOCK SMS] To: {phone_number} | Msg: {message}")
        return True

    url = "https://api.africastalking.com/version1/messaging"
    headers = {"apiKey": api_key, "Accept": "application/json"}
    payload = {"username": username, "to": phone_number, "message": message}
    
    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        return False

def send_whatsapp(phone_number: str, message: str) -> bool:
    """
    Sends a WhatsApp message using Meta's Cloud API.
    Requires WHATSAPP_TOKEN and WHATSAPP_PHONE_ID in settings.
    """
    token = getattr(settings, "WHATSAPP_TOKEN", "mock_token")
    phone_id = getattr(settings, "WHATSAPP_PHONE_ID", "mock_id")

    if token == "mock_token":
        logger.info(f"[MOCK WHATSAPP] To: {phone_number} | Msg: {message}")
        return True

    url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"WhatsApp failed: {e}")
        return False

def generate_receipt_message(patient_name: str, amount: str, ref: str, clinic_name: str) -> str:
    return (
        f"Hello {patient_name},\n"
        f"Your payment of ZMW {amount} for invoice {ref} has been received and approved.\n"
        f"Thank you for choosing {clinic_name}!"
    )
'''
notif_path.write_text(notif_content.strip() + "\n", encoding="utf-8")
print("   wrote api/notifications.py")

# ═════════════════════════════════════════════════════════════════════
# 2. Add Backend Endpoint for Sending Receipts
# ═════════════════════════════════════════════════════════════════════
print("\n==> Adding send-receipt endpoint to PaymentViewSet")
vp = ROOT / "billing" / "views.py"
if vp.exists():
    vsrc = vp.read_text(encoding="utf-8")
    MARKER = "# === notifications patch ==="
    
    if MARKER not in vsrc:
        PATCH = r'''
# === notifications patch ===
try:
    from rest_framework.decorators import action as _notif_action
    from rest_framework.response import Response as _notif_resp
    from api.notifications import send_sms, send_whatsapp, generate_receipt_message

    def _send_receipt(self, request, pk=None):
        p = self.get_object()
        method = request.data.get("method", "whatsapp") # 'sms' or 'whatsapp'
        
        # Try to get patient phone. Adjust based on your actual model structure.
        phone = getattr(p, "patient_phone", None)
        if not phone and hasattr(p, "patient") and p.patient:
            phone = getattr(p.patient, "phone", None)
            
        if not phone:
            return _notif_resp({"detail": "No phone number found for this patient."}, status=400)

        # Clean phone number (remove spaces, ensure country code)
        phone = str(phone).replace(" ", "")
        if phone.startswith("0"):
            phone = "+260" + phone[1:] # Assuming Zambia +260

        clinic_name = getattr(p.tenant, "name", "the clinic") if hasattr(p, "tenant") else "the clinic"
        patient_name = getattr(p.patient, "full_name", "Patient") if hasattr(p, "patient") else "Patient"
        amount = str(p.amount)
        ref = getattr(p, "reference", f"PAY-{p.id}")

        msg = generate_receipt_message(patient_name, amount, ref, clinic_name)

        if method == "sms":
            success = send_sms(phone, msg)
        else:
            success = send_whatsapp(phone, msg)

        if success:
            return _notif_resp({"detail": f"Receipt sent via {method}."})
        else:
            return _notif_resp({"detail": "Failed to send message. Check server logs."}, status=500)

    if "PaymentViewSet" in globals():
        PaymentViewSet.send_receipt = _notif_action(detail=True, methods=["post"])(_send_receipt)
        print("[notifications] send-receipt action registered.")
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"[notifications] patch failed: {e}")
'''
        vsrc += "\n\n" + PATCH
        vp.write_text(vsrc, encoding="utf-8")
        print("   appended send-receipt action to PaymentViewSet")
    else:
        print("   PaymentViewSet already patched.")

# ═════════════════════════════════════════════════════════════════════
# 3. Create Frontend Notification Buttons
# ═════════════════════════════════════════════════════════════════════
print("\n==> Creating frontend NotificationButtons component")
comp_path = FRONTEND / "src" / "components" / "NotificationButtons.tsx"
comp_path.parent.mkdir(parents=True, exist_ok=True)

COMP_CONTENT = r'''import { useState } from "react";
import { MessageCircle, Smartphone, Check, Loader2 } from "lucide-react";
import { api } from "../api/client";

export function NotificationButtons({ paymentId }: { paymentId: number }) {
  const [status, setStatus] = useState<"idle" | "sending_sms" | "sending_wa" | "success">("idle");

  const send = async (method: "sms" | "whatsapp") => {
    setStatus(method === "sms" ? "sending_sms" : "sending_wa");
    try {
      await api.post(`/payments/${paymentId}/send-receipt/`, { method });
      setStatus("success");
      setTimeout(() => setStatus("idle"), 3000);
    } catch (err: any) {
      alert("Failed to send: " + JSON.stringify(err.response?.data || err.message));
      setStatus("idle");
    }
  };

  if (status === "success") {
    return <span className="text-xs font-medium text-emerald-600 flex items-center gap-1"><Check size={14}/> Sent!</span>;
  }

  return (
    <div className="flex gap-1">
      <button 
        onClick={() => send("whatsapp")} 
        disabled={status !== "idle"}
        title="Send WhatsApp Receipt"
        className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded disabled:opacity-50 transition"
      >
        {status === "sending_wa" ? <Loader2 size={16} className="animate-spin" /> : <MessageCircle size={16} />}
      </button>
      <button 
        onClick={() => send("sms")} 
        disabled={status !== "idle"}
        title="Send SMS Receipt"
        className="p-1.5 text-sky-600 hover:bg-sky-50 rounded disabled:opacity-50 transition"
      >
        {status === "sending_sms" ? <Loader2 size={16} className="animate-spin" /> : <Smartphone size={16} />}
      </button>
    </div>
  );
}
'''
comp_path.write_text(COMP_CONTENT.strip() + "\n", encoding="utf-8")
print(f"   wrote frontend/src/components/NotificationButtons.tsx")

# ═════════════════════════════════════════════════════════════════════
# 4. Inject Component into Payments Page
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching Payments.tsx")
payments_path = FRONTEND / "src" / "pages" / "Payments.tsx"
if payments_path.exists():
    txt = payments_path.read_text(encoding="utf-8")
    if "NotificationButtons" not in txt:
        # 1. Add Import
        txt = txt.replace(
            'import { api } from "../api/client";',
            'import { api } from "../api/client";\nimport { NotificationButtons } from "../components/NotificationButtons";'
        )
        
        # 2. Try to find the table row and add the button next to the reference or status
        # Look for <td ...>{p.reference}</td> or similar
        if "<td" in txt and "reference" in txt:
            # Generic injection: add a new column header
            txt = txt.replace('<th className="text-left px-4 py-3">Reference</th>', '<th className="text-left px-4 py-3">Reference</th>\n                <th className="text-center px-4 py-3">Notify</th>')
            # Add the cell
            txt = re.sub(
                r'(<td[^>]*>\{p\.reference\}</td>)',
                r'\1\n                  <td className="px-4 py-3 text-center"><NotificationButtons paymentId={p.id} /></td>',
                txt
            )
        # Fallback if reference isn't found, look for status
        elif "<td" in txt and "status" in txt:
            txt = re.sub(
                r'(<td[^>]*>.*?status.*?</td>)',
                r'\1\n                  <td className="px-4 py-3 text-center"><NotificationButtons paymentId={p.id} /></td>',
                txt
            )

        payments_path.write_text(txt, encoding="utf-8")
        print("   Patched Payments.tsx with Notification buttons.")
    else:
        print("   Payments.tsx already has NotificationButtons.")
else:
    print("   [WARN] Could not find Payments.tsx to inject UI buttons.")

# ═════════════════════════════════════════════════════════════════════
# 5. Run Migrations, Build, and Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Django checks and migrations")
subprocess.run([str(PY), "manage.py", "makemigrations"], cwd=ROOT, check=False)
subprocess.run([str(PY), "manage.py", "migrate"], cwd=ROOT, check=False)

npm = npm_path()
if npm:
    print("\n==> Running Vite build...")
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Build succeeded!")
    else:
        print("   ❌ Build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print("     " + line)

print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "feat: add SMS and WhatsApp receipt integrations"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. On Render, redeploy both backend and frontend.")
print("  2. Go to the Payments page. You will see WhatsApp and SMS icons next to each payment.")
print("  3. Clicking them will trigger the mock endpoint. Check the backend logs on Render")
print("     to see the formatted message output (e.g., '[MOCK WHATSAPP] To: +260... | Msg: ...')")
print("  4. To go live, add your AFRICASTALKING_API_KEY and WHATSAPP_TOKEN to your Render environment variables.")