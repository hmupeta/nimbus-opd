#!/usr/bin/env python3
"""
fix_mtn_api_key_201.py
  - Fixes the status code check for API Key generation (accepts 200 and 201).
  - This allows the backend to capture the key MTN is successfully returning.
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

# 1. Update MTN Service to accept 201 Created
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
        self.base_url = "https://sandbox.momodeveloper.mtn.com" if self.env == "sandbox" else "https://proxy.momoapi.mtn.com"

    def provision_api_user(self, callback_host, subscription_key):
        """Create a real API user and key on MTN Sandbox."""
        ref_id = str(uuid.uuid4()) 
        
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
        # Accept both 200 OK and 201 Created
        if r.status_code not in (200, 201):
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

# 2. Push
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT)
subprocess.run(["git", "commit", "-m", "fix(mtn): accept 201 Created for API key generation"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")