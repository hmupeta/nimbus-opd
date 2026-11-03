#!/usr/bin/env python3
"""
add_integrations_settings.py
1. Creates a database model to store SMS/WhatsApp credentials per clinic.
2. Adds API endpoints to GET and SAVE these settings.
3. Updates the notification service to use the saved credentials.
4. Creates a beautiful UI page for managing these settings.
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
# 1. Backend: Add IntegrationSettings Model
# ═════════════════════════════════════════════════════════════════════
print("==> Adding IntegrationSettings model to tenants/models.py")
model_path = ROOT / "tenants" / "models.py"
src = model_path.read_text(encoding="utf-8")

if "class IntegrationSettings" not in src:
    # Ensure Tenant is imported
    if "class Tenant" not in src:
        sys.exit("Could not find Tenant model in tenants/models.py")
        
    model_code = '''

class IntegrationSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="integration_settings")
    sms_api_key = models.CharField(max_length=255, blank=True, help_text="Africa's Talking API Key")
    sms_sender_id = models.CharField(max_length=50, blank=True, help_text="e.g., NIMBUS")
    whatsapp_phone_id = models.CharField(max_length=255, blank=True, help_text="Meta WhatsApp Phone Number ID")
    whatsapp_token = models.TextField(blank=True, help_text="Meta WhatsApp Permanent Token")

    def __str__(self):
        return f"Integrations for {self.tenant.name}"
'''
    src += model_code
    model_path.write_text(src, encoding="utf-8")
    print("   Added IntegrationSettings model.")
else:
    print("   IntegrationSettings model already exists.")

# ═════════════════════════════════════════════════════════════════════
# 2. Backend: Serializer & View for Settings
# ═════════════════════════════════════════════════════════════════════
print("\n==> Adding Serializer and View for Settings")

# Serializer
serializer_path = ROOT / "tenants" / "serializers.py"
if not serializer_path.exists():
    serializer_path.write_text("from rest_framework import serializers\nfrom .models import IntegrationSettings\n", encoding="utf-8")
else:
    src = serializer_path.read_text(encoding="utf-8")
    if "from .models import IntegrationSettings" not in src:
        src = "from .models import IntegrationSettings\n" + src

src = serializer_path.read_text(encoding="utf-8")
if "class IntegrationSettingsSerializer" not in src:
    src += '''

class IntegrationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSettings
        fields = ["sms_api_key", "sms_sender_id", "whatsapp_phone_id", "whatsapp_token"]
'''
    serializer_path.write_text(src, encoding="utf-8")
    print("   Added IntegrationSettingsSerializer.")

# View
views_path = ROOT / "tenants" / "views.py"
if not views_path.exists():
    views_path.write_text("from rest_framework.views import APIView\nfrom rest_framework.response import Response\nfrom rest_framework.permissions import IsAuthenticated\n", encoding="utf-8")
else:
    src = views_path.read_text(encoding="utf-8")
    if "from rest_framework.views import APIView" not in src:
        src = "from rest_framework.views import APIView\nfrom rest_framework.response import Response\nfrom rest_framework.permissions import IsAuthenticated\n" + src

src = views_path.read_text(encoding="utf-8")
if "class IntegrationSettingsView" not in src:
    src += '''

from .models import IntegrationSettings
from .serializers import IntegrationSettingsSerializer

class IntegrationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({"detail": "No tenant assigned."}, status=400)
        
        obj, _ = IntegrationSettings.objects.get_or_create(tenant=tenant)
        return Response(IntegrationSettingsSerializer(obj).data)

    def put(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return Response({"detail": "No tenant assigned."}, status=400)
        
        obj, _ = IntegrationSettings.objects.get_or_create(tenant=tenant)
        serializer = IntegrationSettingsSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
'''
    views_path.write_text(src, encoding="utf-8")
    print("   Added IntegrationSettingsView.")

# URL Routing
urls_path = ROOT / "tenants" / "urls.py"
if not urls_path.exists():
    urls_path.write_text("from django.urls import path\n", encoding="utf-8")

src = urls_path.read_text(encoding="utf-8")
if "IntegrationSettingsView" not in src:
    src = "from .views import IntegrationSettingsView\n" + src
    if "urlpatterns" not in src:
        src += "\nurlpatterns = []\n"
    src = src.replace("urlpatterns = [", "urlpatterns = [\n    path('settings/', IntegrationSettingsView.as_view(), name='integration-settings'),")
    urls_path.write_text(src, encoding="utf-8")
    print("   Added URL route.")

# Ensure tenants.urls is included in main urls.py
main_urls = ROOT / "api" / "urls.py"
if main_urls.exists():
    msrc = main_urls.read_text(encoding="utf-8")
    if "tenants.urls" not in msrc and "include('tenants.urls')" not in msrc:
        if "from django.urls import path, include" not in msrc:
            msrc = msrc.replace("from django.urls import path", "from django.urls import path, include")
        msrc = msrc.replace("urlpatterns = [", "urlpatterns = [\n    path('integrations/', include('tenants.urls')),")
        main_urls.write_text(msrc, encoding="utf-8")
        print("   Linked tenants.urls to api/urls.py")

# ═════════════════════════════════════════════════════════════════════
# 3. Update Notification Service to use DB Settings
# ═════════════════════════════════════════════════════════════════════
print("\n==> Updating api/notifications.py to use DB settings")
notif_path = ROOT / "api" / "notifications.py"
if notif_path.exists():
    src = notif_path.read_text(encoding="utf-8")
    # We rewrite the file to take 'tenant' as an argument and fetch settings
    notif_content = r'''import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def get_tenant_config(tenant):
    try:
        return tenant.integration_settings
    except Exception:
        return None

def send_sms(phone_number: str, message: str, tenant=None) -> bool:
    config = get_tenant_config(tenant)
    api_key = config.sms_api_key if config and config.sms_api_key else getattr(settings, "AFRICASTALKING_API_KEY", "mock_key")
    sender_id = config.sms_sender_id if config and config.sms_sender_id else "NIMBUS"
    
    if not api_key or api_key == "mock_key":
        logger.info(f"[MOCK SMS] To: {phone_number} | Msg: {message}")
        return True

    # Africa's Talking API integration
    url = "https://api.africastalking.com/version1/messaging"
    headers = {"apiKey": api_key, "Accept": "application/json"}
    payload = {"username": "sandbox", "to": phone_number, "message": message, "from": sender_id}
    
    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        return False

def send_whatsapp(phone_number: str, message: str, tenant=None) -> bool:
    config = get_tenant_config(tenant)
    token = config.whatsapp_token if config and config.whatsapp_token else getattr(settings, "WHATSAPP_TOKEN", "mock_token")
    phone_id = config.whatsapp_phone_id if config and config.whatsapp_phone_id else getattr(settings, "WHATSAPP_PHONE_ID", "mock_id")

    if not token or token == "mock_token":
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

# Update views.py to pass tenant
vp = ROOT / "billing" / "views.py"
if vp.exists():
    vsrc = vp.read_text(encoding="utf-8")
    vsrc = vsrc.replace("send_sms(phone, msg)", "send_sms(phone, msg, tenant=p.tenant)")
    vsrc = vsrc.replace("send_whatsapp(phone, msg)", "send_whatsapp(phone, msg, tenant=p.tenant)")
    vp.write_text(vsrc, encoding="utf-8")

# ═════════════════════════════════════════════════════════════════════
# 4. Frontend: Create Integrations Page
# ═════════════════════════════════════════════════════════════════════
print("\n==> Creating frontend Integrations.tsx page")
fe_path = FRONTEND / "src" / "pages" / "Integrations.tsx"
fe_path.parent.mkdir(parents=True, exist_ok=True)

FE_CONTENT = r'''import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { MessageSquare, Smartphone, Save, Loader2, Key } from "lucide-react";

export default function Integrations() {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    sms_api_key: "",
    sms_sender_id: "",
    whatsapp_phone_id: "",
    whatsapp_token: "",
  });
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: async () => (await api.get("/integrations/settings/")).data,
  });

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: async () => (await api.put("/integrations/settings/", form)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  if (isLoading) return <div className="p-8">Loading settings...</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Integrations & API Keys</h1>
        <p className="text-sm text-slate-500 mt-1">Manage your SMS and WhatsApp communication settings for this clinic.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* SMS Settings */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-sky-100 p-2 rounded-lg"><Smartphone className="h-5 w-5 text-sky-600" /></div>
            <h2 className="text-lg font-semibold text-slate-800">SMS Settings (Africa's Talking)</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
              <input type="password" name="sms_api_key" value={form.sms_api_key || ""} onChange={handleChange}
                     placeholder="atsk_..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Sender ID / Shortcode</label>
              <input type="text" name="sms_sender_id" value={form.sms_sender_id || ""} onChange={handleChange}
                     placeholder="e.g., NIMBUS"
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none transition" />
            </div>
          </div>
        </div>

        {/* WhatsApp Settings */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-emerald-100 p-2 rounded-lg"><MessageSquare className="h-5 w-5 text-emerald-600" /></div>
            <h2 className="text-lg font-semibold text-slate-800">WhatsApp Settings (Meta Cloud API)</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number ID</label>
              <input type="text" name="whatsapp_phone_id" value={form.whatsapp_phone_id || ""} onChange={handleChange}
                     placeholder="e.g., 1045..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Permanent Access Token</label>
              <input type="password" name="whatsapp_token" value={form.whatsapp_token || ""} onChange={handleChange}
                     placeholder="EAAL..."
                     className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none transition" />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 pt-4">
        <button onClick={() => save.mutate()} disabled={save.isPending}
                className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-6 py-2.5 rounded-lg font-medium transition disabled:opacity-50">
          {save.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          Save Settings
        </button>
        {saved && <span className="text-emerald-600 text-sm font-medium flex items-center gap-1"><Key className="h-4 w-4"/> Settings saved securely.</span>}
      </div>
    </div>
  );
}
'''
fe_path.write_text(FE_CONTENT.strip() + "\n", encoding="utf-8")
print("   Created Integrations.tsx.")

# ═════════════════════════════════════════════════════════════════════
# 5. Run Migrations, Build, and Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Django migrations...")
subprocess.run([str(PY), "manage.py", "makemigrations", "tenants"], cwd=ROOT, check=False)
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
    subprocess.run(["git", "commit", "-m", "feat: add integrations settings UI and DB storage"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. Deploy both backend and frontend on Render.")
print("  2. Go to the 'Integrations' link in the sidebar.")
print("  3. You will see a secure form to paste your Africa's Talking API Key and Meta WhatsApp Token.")
print("  4. Save them, and the background notification service will immediately start using them.")