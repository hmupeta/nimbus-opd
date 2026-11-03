import logging
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
