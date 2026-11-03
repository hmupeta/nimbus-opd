import logging
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
