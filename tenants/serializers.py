from rest_framework import serializers
from .models import IntegrationSettings


class IntegrationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSettings
        fields = [
            "sms_api_key", "sms_sender_id", 
            "whatsapp_phone_id", "whatsapp_token",
            "momo_api_key", "momo_provider",
            "stripe_public_key", "stripe_secret_key"
        ]
