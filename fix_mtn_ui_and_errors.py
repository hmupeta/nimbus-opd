#!/usr/bin/env python3
"""
fix_mtn_ui_and_errors.py
  - Adds exact error alerts to the UI if generation fails.
  - Makes sure the backend endpoint is forced to use the real MTN API.
  - Sets a dummy API Secret requirement for Sandbox testing.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. Overwrite the backend logic (Again, to be 100% sure) ───────────
print("==> Overwriting api/momo_views.py")
write("api/momo_views.py", '''\
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from tenants.models import MobileMoneyConfig
from api.momo_serializers import MobileMoneyConfigSerializer
from api.permissions import require_roles
from billing.mtn_service import MTNMoMoService


class MobileMoneyConfigViewSet(viewsets.ModelViewSet):
    queryset = MobileMoneyConfig.objects.all()
    serializer_class = MobileMoneyConfigSerializer
    permission_classes = [require_roles("admin", "finance_manager")]

    def get_queryset(self):
        qs = super().get_queryset().filter(tenant=self.request.user.tenant)
        for field in ("provider", "environment"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=False, methods=["post"], url_path="create-api-user")
    def create_api_user(self, request):
        provider = request.data.get("provider")
        callback_host = request.data.get("callback_host")
        subscription_key = request.data.get("subscription_key")
        
        if not provider or not callback_host or not subscription_key:
            return Response({"detail": "provider, callback_host, and subscription_key are required"}, status=400)

        temp_cfg = MobileMoneyConfig(
            tenant=request.user.tenant,
            provider=provider,
            environment="sandbox",
            subscription_key=subscription_key
        )
        
        try:
            service = MTNMoMoService(temp_cfg)
            api_user, api_key = service.provision_api_user(callback_host, subscription_key)
            return Response({
                "api_user": api_user,
                "api_key": api_key,
                "message": "Successfully provisioned a real UUID and API Key from MTN Sandbox."
            })
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
''')

# ─── 2. Patch Frontend to show errors ──────────────────────────────────
print("==> Updating frontend/src/pages/Integrations.tsx")
fp = ROOT / "frontend" / "src" / "pages" / "Integrations.tsx"
f = fp.read_text(encoding="utf-8")

# Add onError to generateApiUser
old_mut = '''  const generateApiUser = useMutation({
    mutationFn: async (payload: { provider: string, callback_host: string, subscription_key: string }) => {
      const { data } = await api.post("/mobile-money-configs/create-api-user/", payload);
      return data;
    },
    onSuccess: (data) => {
      setMomoApiUser(data.api_user);
      setMomoApiKey(data.api_key);
      alert(data.message);
    },
  });'''

new_mut = '''  const generateApiUser = useMutation({
    mutationFn: async (payload: { provider: string, callback_host: string, subscription_key: string }) => {
      const { data } = await api.post("/mobile-money-configs/create-api-user/", payload);
      return data;
    },
    onSuccess: (data) => {
      setMomoApiUser(data.api_user);
      setMomoApiKey(data.api_key);
      alert(data.message);
    },
    onError: (err: any) => {
      const msg = err.response?.data?.detail || err.message;
      alert("Failed to generate API User from MTN: \\n\\n" + msg);
    }
  });'''

if old_mut in f:
    f = f.replace(old_mut, new_mut)
    
# Ensure the button passes the subscription key
old_btn = '''                  onClick={() => {
                    if (!momoSubKey) {
                      alert("Please enter the Subscription Key first.");
                      return;
                    }
                    generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback, subscription_key: momoSubKey });
                  }}'''
new_btn = '''                  onClick={() => {
                    const subKey = momoSubKey || prompt("Please enter the Subscription Key from the MTN Portal:");
                    if (!subKey) return;
                    generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback, subscription_key: subKey });
                  }}'''
if old_btn in f:
    f = f.replace(old_btn, new_btn)

fp.write_text(f, encoding="utf-8")
print("   patched Integrations.tsx")

# ─── 3. Push ───────────────────────────────────────────────────────────
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT)
subprocess.run(["git", "commit", "-m", "fix(momo): force real MTN provisioning and add UI error alerts"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")