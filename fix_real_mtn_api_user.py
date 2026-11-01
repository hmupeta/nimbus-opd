#!/usr/bin/env python3
"""
fix_real_mtn_api_user.py
  - Corrects the MTN API User generation to use a real UUID v4.
  - Actually calls the MTN sandbox API to provision the user and key.
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
        # For sandbox, the URL is https://sandbox.momodeveloper.mtn.com
        self.base_url = "https://sandbox.momodeveloper.mtn.com" if self.env == "sandbox" else "https://proxy.momoapi.mtn.com"

    def provision_api_user(self, callback_host, subscription_key):
        """Create a real API user and key on MTN Sandbox."""
        ref_id = str(uuid.uuid4()) # MTN requires a UUID v4 for the API User
        
        # 1. Create the API User
        url = f"{self.base_url}/v1_0/apiuser"
        headers = {
            "X-Reference-Id": ref_id,
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Content-Type": "application/json"
        }
        payload = {"providerCallbackHost": callback_host}
        
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code != 201:
            raise Exception(f"Failed to create API user: {r.text}")
        
        # 2. Get the API Key for that user
        url = f"{self.base_url}/v1_0/apiuser/{ref_id}/apikey"
        headers = {"Ocp-Apim-Subscription-Key": subscription_key}
        
        r = requests.post(url, headers=headers, timeout=15)
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

# 2. Update views to use the new provisioning method
print("==> Updating api/momo_views.py")
vp = ROOT / "api" / "momo_views.py"
v = vp.read_text(encoding="utf-8")

import re
pattern = re.compile(r"    @action\(detail=False, methods=\[\"post\"\], url_path=\"create-api-user\"\).*?(?=\n    @action|\Z)", re.DOTALL)
new_create = '''    @action(detail=False, methods=["post"], url_path="create-api-user")
    def create_api_user(self, request):
        provider = request.data.get("provider")
        callback_host = request.data.get("callback_host")
        subscription_key = request.data.get("subscription_key")
        
        if not provider or not callback_host or not subscription_key:
            return Response({"detail": "provider, callback_host, and subscription_key are required"}, status=400)

        from billing.mtn_service import MTNMoMoService
        from tenants.models import MobileMoneyConfig
        
        temp_cfg = MobileMoneyConfig(
            tenant=request.user.tenant,
            provider=provider,
            environment="sandbox",
            subscription_key=subscription_key
        )
        
        try:
            service = MTNMoMoService(temp_cfg)
            # Now calls the real MTN API to provision a UUID and Key
            api_user, api_key = service.provision_api_user(callback_host, subscription_key)
            return Response({
                "api_user": api_user,
                "api_key": api_key,
                "message": "Successfully provisioned a real API User on MTN Sandbox."
            })
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
'''
v = pattern.sub(new_create, v, count=1)
vp.write_text(v, encoding="utf-8")
print("   patched api/momo_views.py")

# 3. Push
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT)
subprocess.run(["git", "commit", "-m", "fix(momo): real UUID provisioning for MTN API users"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")