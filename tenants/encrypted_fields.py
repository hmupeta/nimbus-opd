import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = getattr(settings, "MOBILE_MONEY_ENCRYPTION_KEY", None)
    if not key:
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """TextField whose values are encrypted at rest with Fernet (AES-128 + HMAC).

    Falls back to returning the raw value if decryption fails (e.g. key changed).
    That way, an accidental SECRET_KEY rotation makes the field visibly broken
    in the admin rather than crashing the whole page — the admin can then
    re-enter the value.
    """

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            logger.warning("EncryptedTextField: decryption failed "
                           "(encryption key changed?). Returning raw.")
            return value

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _get_fernet().encrypt(str(value).encode()).decode()
