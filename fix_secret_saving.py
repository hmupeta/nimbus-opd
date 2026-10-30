#!/usr/bin/env python3
"""
fix_secret_saving.py
  - Fixes the MobileMoneyConfigSerializer and PaymentGatewayConfigSerializer
    so they correctly save API keys and secrets to the database.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. Fix MobileMoneyConfigSerializer ────────────────────────────────
print("==> Patching api/momo_serializers.py")
write("api/momo_serializers.py", '''\
from rest_framework import serializers
from tenants.models import MobileMoneyConfig


class MobileMoneyConfigSerializer(serializers.ModelSerializer):
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
            "merchant_code", "short_code", "api_user", "callback_host",
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

    def _filter_secrets(self, validated):
        """Remove empty secret fields from validated so they don't overwrite existing values.
        Keep non-empty fields so super().create() and super().update() save them."""
        for field in ("api_key", "api_secret", "api_password", "subscription_key"):
            if field in validated and not validated[field]:
                validated.pop(field)
        return validated

    def create(self, validated):
        request = self.context["request"]
        validated["tenant"] = request.user.tenant
        validated = self._filter_secrets(validated)
        return super().create(validated)

    def update(self, instance, validated):
        validated = self._filter_secrets(validated)
        return super().update(instance, validated)

    def validate(self, data):
        if data.get("is_default") and not data.get("is_active", getattr(
                self.instance, "is_active", False)):
            raise serializers.ValidationError(
                "A default config must also be active.")
        return data
''')

# ─── 2. Fix PaymentGatewayConfigSerializer ─────────────────────────────
print("==> Patching api/gateway_serializers.py")
write("api/gateway_serializers.py", '''\
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

    def get_secret_key_set(self, obj) -> bool:     return bool(obj.secret_key)
    def get_webhook_secret_set(self, obj) -> bool: return bool(obj.webhook_secret)

    def _filter_secrets(self, validated):
        for field in ("secret_key", "webhook_secret"):
            if field in validated and not validated[field]:
                validated.pop(field)
        return validated

    def create(self, validated):
        request = self.context["request"]
        validated["tenant"] = request.user.tenant
        validated = self._filter_secrets(validated)
        return super().create(validated)

    def update(self, instance, validated):
        validated = self._filter_secrets(validated)
        return super().update(instance, validated)

    def validate(self, data):
        if data.get("is_default") and not data.get("is_active", getattr(
                self.instance, "is_active", False)):
            raise serializers.ValidationError("A default config must be active.")
        return data
''')

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(api): correctly save secrets in mobile money and gateway configs", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")