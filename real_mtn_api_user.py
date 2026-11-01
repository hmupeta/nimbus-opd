#!/usr/bin/env python3
"""
real_mtn_api_user.py
  - Updates MTNMoMoService to include create_api_user.
  - Updates the momo_views to use it.
  - Updates the frontend to pass the subscription key.
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

# 1. Update MTN Service
print("==> Updating billing/mtn_service.py")
write("billing/mtn_service.py", '''\
import base64
import uuid
import requests
from decimal import Decimal
from tenants.models import MobileMoneyConfig

class MTNMoMoService:
    def __init__(self, config: MobileMoneyConfig):
        self.config = config
        self.env = "sandbox" if config.environment == "sandbox" else "mtnzambia"
        self.base_url = f"https://{self.env}.momodeveloper.mtn.com" if self.env == "sandbox" else "https://proxy.momoapi.mtn.com"

    def create_api_user(self, callback_host):
        """Create a real API user and key on MTN Sandbox."""
        ref_id = str(uuid.uuid4())
        url = f"{self.base_url}/v1_0/apiuser"
        headers = {
            "X-Reference-Id": ref_id,
            "Ocp-Apim-Subscription-Key": self.config.subscription_key,
            "Content-Type": "application/json"
        }
        r = requests.post(url, headers=headers, json={"providerCallbackHost": callback_host})
        if r.status_code != 201:
             raise Exception(f"Failed to create API user: {r.text}")
        
        # Get API Key
        url = f"{self.base_url}/v1_0/apiuser/{ref_id}/apikey"
        headers = {"Ocp-Apim-Subscription-Key": self.config.subscription_key}
        r = requests.post(url, headers=headers)
        if r.status_code != 200:
             raise Exception(f"Failed to get API key: {r.text}")
        
        return ref_id, r.json()["apiKey"]

    def _get_token(self):
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
        token = self._get_token()
        url = f"{self.base_url}/collection/v1_0/requesttopay"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": self.env,
            "Ocp-Apim-Subscription-Key": self.config.subscription_key,
            "Content-Type": "application/json",
        }
        currency = "EUR" if self.env == "sandbox" else "ZMW"
        payload = {
            "amount": str(amount),
            "currency": currency,
            "externalId": external_id,
            "payer": {"partyIdType": "MSISDN", "partyId": phone},
            "payerMessage": payer_message,
            "payeeNote": "Payment to Nimbus OPD"
        }
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code != 202:
            raise Exception(f"Request failed: {r.text}")
        return True

    def check_status(self, reference_id):
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

# 2. Update views to use the real method
print("==> Updating api/momo_views.py")
vp = ROOT / "api" / "momo_views.py"
v = vp.read_text(encoding="utf-8")

old_create = '''    @action(detail=False, methods=["post"], url_path="create-api-user")
    def create_api_user(self, request):
        import uuid
        provider = request.data.get("provider")
        callback_host = request.data.get("callback_host")
        
        if not provider or not callback_host:
            return Response({"detail": "provider and callback_host are required"}, status=400)

        generated_user = f"user_{uuid.uuid4().hex[:10]}"
        generated_key = f"key_{uuid.uuid4().hex[:16]}"
        
        return Response({
            "api_user": generated_user,
            "api_key": generated_key,
            "message": f"Successfully provisioned API User for {provider}."
        })'''

new_create = '''    @action(detail=False, methods=["post"], url_path="create-api-user")
    def create_api_user(self, request):
        provider = request.data.get("provider")
        callback_host = request.data.get("callback_host")
        subscription_key = request.data.get("subscription_key")
        
        if not provider or not callback_host or not subscription_key:
            return Response({"detail": "provider, callback_host, and subscription_key are required"}, status=400)

        from billing.mtn_service import MTNMoMoService
        from tenants.models import MobileMoneyConfig
        
        # Create an unsaved config instance to use the service
        temp_cfg = MobileMoneyConfig(
            tenant=request.user.tenant,
            provider=provider,
            environment="sandbox",
            subscription_key=subscription_key
        )
        
        try:
            service = MTNMoMoService(temp_cfg)
            api_user, api_key = service.create_api_user(callback_host)
            return Response({
                "api_user": api_user,
                "api_key": api_key,
                "message": "Successfully provisioned a real API User on MTN Sandbox."
            })
        except Exception as e:
            return Response({"detail": str(e)}, status=400)'''

if old_create in v:
    v = v.replace(old_create, new_create)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/momo_views.py")

# 3. Update Frontend
print("==> Updating src/pages/Integrations.tsx")
fp = ROOT / "frontend" / "src" / "pages" / "Integrations.tsx"
f = fp.read_text(encoding="utf-8")

# Change mutation to pass subscription key
old_mutation = '''  const generateApiUser = useMutation({
    mutationFn: async (payload: { provider: string, callback_host: string }) => {
      const { data } = await api.post("/mobile-money-configs/create-api-user/", payload);
      return data;
    },'''
new_mutation = '''  const generateApiUser = useMutation({
    mutationFn: async (payload: { provider: string, callback_host: string, subscription_key: string }) => {
      const { data } = await api.post("/mobile-money-configs/create-api-user/", payload);
      return data;
    },'''

if old_mutation in f:
    f = f.replace(old_mutation, new_mutation)

# Change the button click handler
old_btn = '''                  onClick={() => generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback })}'''
new_btn = '''                  onClick={() => {
                    if (!momoSubKey) {
                      alert("Please enter the Subscription Key first.");
                      return;
                    }
                    generateApiUser.mutate({ provider: momoProvider, callback_host: momoCallback, subscription_key: momoSubKey });
                  }}'''

if old_btn in f:
    f = f.replace(old_btn, new_btn)

fp.write_text(f, encoding="utf-8")
print("   patched Integrations.tsx")

# 4. Push
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT)
subprocess.run(["git", "commit", "-m", "feat(momo): real API user provisioning against MTN Sandbox"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")