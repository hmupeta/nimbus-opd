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