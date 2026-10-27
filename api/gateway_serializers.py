from rest_framework import serializers
from tenants.models import PaymentGatewayConfig


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    secret_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={"input_type": "password"})
    webhook_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={"input_type": "password"})

    secret_key_set = serializers.SerializerMethodField()
    webhook_secret_set = serializers.SerializerMethodField()

    class Meta:
        model = PaymentGatewayConfig
        fields = [
            "id", "provider", "environment", "publishable_key",
            "secret_key", "webhook_secret",
            "secret_key_set", "webhook_secret_set",
            "is_active", "is_default",
            "last_verified_at", "last_verification_status",
            "last_verification_message",
        ]
        read_only_fields = [
            "id", "last_verified_at", "last_verification_status",
            "last_verification_message",
        ]

    def get_secret_key_set(self, obj) -> bool: return bool(obj.secret_key)
    def get_webhook_secret_set(self, obj) -> bool: return bool(obj.webhook_secret)

    def _apply_secrets(self, instance, validated):
        for field in ("secret_key", "webhook_secret"):
            if field in validated and validated[field]:
                setattr(instance, field, validated.pop(field))
            else:
                validated.pop(field, None)
        return validated

    def create(self, validated):
        request = self.context["request"]
        validated["tenant"] = request.user.tenant
        validated = self._apply_secrets(PaymentGatewayConfig(), validated)
        return super().create(validated)

    def update(self, instance, validated):
        validated = self._apply_secrets(instance, validated)
        return super().update(instance, validated)

    def validate(self, data):
        if data.get("is_default") and not data.get("is_active", getattr(
                self.instance, "is_active", False)):
            raise serializers.ValidationError("A default config must be active.")
        return data
