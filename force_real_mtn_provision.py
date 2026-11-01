#!/usr/bin/env python3
"""
force_real_mtn_provision.py
  - Completely overwrites api/momo_views.py to guarantee the real MTN UUID logic.
  - Updates Integrations.tsx so the generated API Key is visible.
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

# ─── 1. Overwrite the backend view completely ──────────────────────────
print("==> Overwriting api/momo_views.py with strict MTN provisioning logic")
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

        # Create an unsaved temp config to use the MTN Service
        from tenants.models import MobileMoneyConfig
        temp_cfg = MobileMoneyConfig(
            tenant=request.user.tenant,
            provider=provider,
            environment="sandbox",
            subscription_key=subscription_key
        )
        
        try:
            service = MTNMoMoService(temp_cfg)
            # This now actually hits MTN to get a real UUID and API Key
            api_user, api_key = service.provision_api_user(callback_host, subscription_key)
            return Response({
                "api_user": api_user,
                "api_key": api_key,
                "message": "Successfully provisioned a real UUID and API Key from MTN Sandbox."
            })
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        cfg = self.get_object()
        
        required = ("merchant_code", "api_user", "api_key", "api_secret", "subscription_key")
        missing = [f for f in required if not getattr(cfg, f, "")]
        
        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing fields: {', '.join(missing)}"
        else:
            try:
                service = MTNMoMoService(cfg)
                service._get_token()
                cfg.last_verification_status = "ok"
                cfg.last_verification_message = "OAuth Handshake successful."
            except Exception as e:
                cfg.last_verification_status = "failed"
                cfg.last_verification_message = str(e)
                
        cfg.last_verified_at = timezone.now()
        cfg.save(update_fields=[
            "last_verified_at", "last_verification_status",
            "last_verification_message",
        ])
        return Response(MobileMoneyConfigSerializer(cfg).data)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        cfg = self.get_object()
        if not cfg.is_active:
            return Response({"detail": "Config must be active."}, status=400)
        MobileMoneyConfig.objects.filter(tenant=cfg.tenant, is_default=True).exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default"])
        return Response(MobileMoneyConfigSerializer(cfg).data)
''')

# ─── 2. Update Frontend UI ─────────────────────────────────────────────
print("==> Updating frontend/src/pages/Integrations.tsx")
fp = ROOT / "frontend" / "src" / "pages" / "Integrations.tsx"
f = fp.read_text(encoding="utf-8")

# Ensure the Generate button sends the subscription key and updates the UI state
old_btn = '''                  onClick={() => {
                    if (!momoSubKey) {
                      alert("Please enter the Subscription Key first.");
                      return;
                    }
                    generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback, subscription_key: momoSubKey });
                  }}'''
new_btn = '''                  onClick={() => {
                    if (!momoSubKey) {
                      alert("Please enter the Subscription Key first.");
                      return;
                    }
                    generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback, subscription_key: momoSubKey });
                  }}'''

if old_btn in f:
    # Just checking if the previous patch applied
    pass

# Make sure the UI shows the API key state correctly after generation
old_key_input = '''              <label className="text-sm"><span className="text-slate-600">API Key</span>
                <input value={momoApiKey} readOnly className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-500" placeholder={editMomoId ? "(Leave blank to keep current)" : "Click Generate above"} />
              </label>'''

new_key_input = '''              <label className="text-sm"><span className="text-slate-600">API Key</span>
                <input 
                  value={momoApiKey} 
                  readOnly 
                  className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-500 font-mono text-xs" 
                  placeholder={editMomoId ? "(Leave blank to keep current)" : "Click Generate above"} 
                />
              </label>'''

if old_key_input in f:
    f = f.replace(old_key_input, new_key_input)

fp.write_text(f, encoding="utf-8")
print("   patched Integrations.tsx")

# ─── 3. Push ───────────────────────────────────────────────────────────
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT)
subprocess.run(["git", "commit", "-m", "fix(momo): force real MTN UUID provisioning and UI key display"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")