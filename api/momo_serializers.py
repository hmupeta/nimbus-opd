from rest_framework import serializers

from tenants.models import MobileMoneyConfig


class MobileMoneyConfigSerializer(serializers.ModelSerializer):
    """Secrets are write-only; their presence is exposed as `*_set` booleans."""

    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={"input_type": "password"},
    )
    api_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={"input_type": "password"},
    )
    api_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={"input_type": "password"},
    )
    subscription_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={"input_type": "password"},
    )

    api_key_set = serializers.SerializerMethodField()
    api_secret_set = serializers.SerializerMethodField()
    api_password_set = serializers.SerializerMethodField()
    subscription_key_set = serializers.SerializerMethodField()

    class Meta:
        model = MobileMoneyConfig
        fields = [
            "id", "provider", "display_name", "environment",
            "merchant_code", "short_code",
            "api_key", "api_secret", "api_password", "subscription_key",
            "api_key_set", "api_secret_set", "api_password_set",
            "subscription_key_set",
            "callback_url", "is_active", "is_default",
            "last_verified_at", "last_verification_status",
            "last_verification_message",
        ]
        read_only_fields = [
            "id", "last_verified_at", "last_verification_status",
            "last_verification_message",
        ]

    def get_api_key_set(self, obj) -> bool:          return bool(obj.api_key)
    def get_api_secret_set(self, obj) -> bool:       return bool(obj.api_secret)
    def get_api_password_set(self, obj) -> bool:     return bool(obj.api_password)
    def get_subscription_key_set(self, obj) -> bool: return bool(obj.subscription_key)

    def _apply_secrets(self, instance, validated):
        """Only overwrite a secret when the client sent a non-empty value."""
        for field in ("api_key", "api_secret", "api_password", "subscription_key"):
            if field in validated and validated[field]:
                setattr(instance, field, validated.pop(field))
            else:
                validated.pop(field, None)
        return validated

    def create(self, validated):
        request = self.context["request"]
        validated["tenant"] = request.user.tenant
        validated = self._apply_secrets(MobileMoneyConfig(), validated)
        return super().create(validated)

    def update(self, instance, validated):
        validated = self._apply_secrets(instance, validated)
        return super().update(instance, validated)

    def validate(self, data):
        if data.get("is_default") and not data.get("is_active", getattr(
                self.instance, "is_active", False)):
            raise serializers.ValidationError(
                "A default config must also be active.")
        return data
