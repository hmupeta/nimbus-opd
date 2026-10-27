#!/usr/bin/env python3
"""
add_mobile_money.py -- per-tenant mobile money configuration + Payment FK.
"""
from __future__ import annotations

import os
import re
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


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Install cryptography ───────────────────────────────────────────
print("==> Installing cryptography")
sh(PY, "-m", "pip", "install", "--quiet", "cryptography>=42")

# ─── 2. EncryptedTextField ─────────────────────────────────────────────
write("tenants/encrypted_fields.py", '''\
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
''')

# ─── 3. Extend tenants/models.py ───────────────────────────────────────
print("==> Patching tenants/models.py")
tp = ROOT / "tenants" / "models.py"
t = tp.read_text(encoding="utf-8")

# Add import
if "from .encrypted_fields import EncryptedTextField" not in t:
    t = t.replace(
        "from django.db import models",
        "from django.db import models\nfrom .encrypted_fields import EncryptedTextField",
    )

# Add enable_mobile_money to TenantSettings
if "enable_mobile_money" not in t:
    t = t.replace(
        "    enable_audit_logs = models.BooleanField(default=True)",
        "    enable_audit_logs = models.BooleanField(default=True)\n"
        "    enable_mobile_money = models.BooleanField(default=False)",
    )

# Append MobileMoneyConfig if not present
if "class MobileMoneyConfig" not in t:
    t += '''


class MobileMoneyProvider(models.TextChoices):
    MTN_MOMO      = "mtn_momo", "MTN Mobile Money"
    AIRTEL_MONEY  = "airtel_money", "Airtel Money"
    ZAMTEL_KWACHA = "zamtel_kwacha", "Zamtel Kwacha"
    MPESA         = "mpesa", "M-Pesa"
    ORANGE_MONEY  = "orange_money", "Orange Money"
    OTHER         = "other", "Other"


class MobileMoneyConfig(models.Model):
    """Per-tenant mobile money merchant configuration.

    Secrets (api_key / api_secret / api_password / subscription_key) are
    encrypted with Fernet keyed from SECRET_KEY (or MOBILE_MONEY_ENCRYPTION_KEY).
    """

    class Environment(models.TextChoices):
        SANDBOX    = "sandbox", "Sandbox"
        PRODUCTION = "production", "Production"

    # Tenant FK must match TenantAwareModel convention for RLS
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)

    provider = models.CharField(max_length=32, choices=MobileMoneyProvider.choices)
    display_name = models.CharField(
        max_length=64, blank=True,
        help_text="Optional label, e.g. 'Main reception line'",
    )
    environment = models.CharField(
        max_length=16, choices=Environment.choices,
        default=Environment.SANDBOX,
    )

    # Public identifiers (safe to display)
    merchant_code = models.CharField(
        max_length=64,
        help_text="Merchant / Paybill / Till number",
    )
    short_code = models.CharField(max_length=16, blank=True)

    # Encrypted secrets
    api_key = EncryptedTextField(blank=True)
    api_secret = EncryptedTextField(blank=True)
    api_password = EncryptedTextField(blank=True)
    subscription_key = EncryptedTextField(blank=True)

    callback_url = models.URLField(
        blank=True,
        help_text="Where the provider posts payment notifications",
    )

    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(
        default=False,
        help_text="Use as default for mobile-money payments",
    )

    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_verification_status = models.CharField(max_length=32, blank=True)
    last_verification_message = models.TextField(blank=True)

    objects = models.Manager()

    class Meta:
        ordering = ["provider", "-is_default"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider", "environment"],
                name="uniq_momo_per_provider_env",
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_default=True, is_active=True),
                name="uniq_default_momo_per_tenant",
            ),
        ]

    def __str__(self):
        label = self.display_name or self.get_provider_display()
        return f"{label} ({self.environment})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_default and not self.is_active:
            raise ValidationError("A default config must be active.")

    def secrets_status(self) -> dict:
        """Booleans indicating whether each secret is set — safe to show via API."""
        return {
            "api_key":          bool(self.api_key),
            "api_secret":       bool(self.api_secret),
            "api_password":     bool(self.api_password),
            "subscription_key": bool(self.subscription_key),
        }
'''
tp.write_text(t, encoding="utf-8")

# ─── 4. Extend tenants/admin.py ────────────────────────────────────────
print("==> Patching tenants/admin.py")
ap = ROOT / "tenants" / "admin.py"
a = ap.read_text(encoding="utf-8")

if "MobileMoneyConfigAdmin" not in a:
    a = a.replace(
        "from .models import Tenant, TenantSequence, TenantSettings, User",
        "from django import forms\nfrom .models import (\n"
        "    MobileMoneyConfig, Tenant, TenantSequence, TenantSettings, User,\n"
        ")",
    )
    a += '''


class MobileMoneyConfigAdmin(admin.ModelAdmin):
    list_display = (
        "provider", "display_name", "environment", "merchant_code",
        "is_active", "is_default", "last_verified_at",
    )
    list_filter = ("provider", "environment", "is_active", "is_default")
    search_fields = ("merchant_code", "display_name")
    readonly_fields = (
        "last_verified_at", "last_verification_status", "last_verification_message",
    )
    fieldsets = (
        ("Identity", {
            "fields": ("tenant", "provider", "display_name", "environment"),
        }),
        ("Merchant", {"fields": ("merchant_code", "short_code")}),
        ("API credentials (encrypted at rest)", {
            "fields": ("api_key", "api_secret", "api_password", "subscription_key"),
            "description": "Values are encrypted with Fernet before storage. "
                           "Leave blank to keep the current value.",
        }),
        ("Webhook", {"fields": ("callback_url",)}),
        ("State", {"fields": ("is_active", "is_default")}),
        ("Verification", {
            "fields": ("last_verified_at", "last_verification_status",
                       "last_verification_message"),
        }),
    )

    def get_queryset(self, request):
        from common.context import get_current_tenant
        qs = super().get_queryset(request)
        if request.user.is_platform_admin or request.user.is_superuser:
            return qs
        t = get_current_tenant() or getattr(request.user, "tenant", None)
        return qs.filter(tenant=t) if t else qs.none()

    def save_model(self, request, obj, form, change):
        from common.context import get_current_tenant
        if not obj.tenant_id:
            t = get_current_tenant() or getattr(request.user, "tenant", None)
            if t:
                obj.tenant = t
        super().save_model(request, obj, form, change)

    # Password-style inputs for secrets
    formfield_overrides = {
        # (imported lazily below to avoid top-of-file import churn)
    }

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Apply password widgets to encrypted fields
        for name in ("api_key", "api_secret", "api_password", "subscription_key"):
            if name in form.base_fields:
                form.base_fields[name].widget = forms.PasswordInput(render_value=True)
                form.base_fields[name].required = False
        return form


admin.site.register(MobileMoneyConfig, MobileMoneyConfigAdmin)
'''
    ap.write_text(a, encoding="utf-8")

# ─── 5. Extend billing/models.py — add FK to Payment ───────────────────
print("==> Patching billing/models.py")
bp = ROOT / "billing" / "models.py"
b = bp.read_text(encoding="utf-8")

if "mobile_money_config" not in b:
    b = b.replace(
        '    reference = models.CharField(max_length=128, blank=True)\n'
        '    paid_at = models.DateTimeField(default=timezone.now)',
        '    reference = models.CharField(max_length=128, blank=True)\n'
        '    mobile_money_config = models.ForeignKey(\n'
        '        "tenants.MobileMoneyConfig",\n'
        '        on_delete=models.PROTECT,\n'
        '        null=True, blank=True,\n'
        '        related_name="payments",\n'
        '        help_text="Required when method=mobile_money",\n'
        '    )\n'
        '    paid_at = models.DateTimeField(default=timezone.now)',
    )
    bp.write_text(b, encoding="utf-8")

# ─── 6. Extend billing/admin.py — show FK in PaymentInline ─────────────
print("==> Patching billing/admin.py")
bap = ROOT / "billing" / "admin.py"
ba = bap.read_text(encoding="utf-8")
if "mobile_money_config" not in ba:
    ba = ba.replace(
        'fields = ("amount", "method", "reference", "paid_at", "received_by")',
        'fields = ("amount", "method", "reference", "mobile_money_config",\n'
        '                  "paid_at", "received_by")',
    )
    ba = ba.replace(
        '    list_display = ("invoice", "amount", "method", "reference",\n'
        '                    "paid_at", "received_by")',
        '    list_display = ("invoice", "amount", "method", "reference",\n'
        '                    "mobile_money_config", "paid_at", "received_by")',
    )
    bap.write_text(ba, encoding="utf-8")

# ─── 7. Extend api/billing_serializers.py — expose FK ──────────────────
print("==> Patching api/billing_serializers.py")
bs = ROOT / "api" / "billing_serializers.py"
bser = bs.read_text(encoding="utf-8")
if "mobile_money_config" not in bser:
    bser = bser.replace(
        '        fields = ["id", "invoice", "amount", "method", "reference",\n'
        '                  "paid_at", "received_by", "notes"]',
        '        fields = ["id", "invoice", "amount", "method", "reference",\n'
        '                  "mobile_money_config", "paid_at", "received_by", "notes"]',
    )
    bs.write_text(bser, encoding="utf-8")

# ─── 8. api/momo_serializers.py ────────────────────────────────────────
write("api/momo_serializers.py", '''\
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

    def get_api_key_set(self, obj):          return bool(obj.api_key)
    def get_api_secret_set(self, obj):       return bool(obj.api_secret)
    def get_api_password_set(self, obj):     return bool(obj.api_password)
    def get_subscription_key_set(self, obj): return bool(obj.subscription_key)

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
''')

# ─── 9. api/momo_views.py ──────────────────────────────────────────────
write("api/momo_views.py", '''\
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from tenants.models import MobileMoneyConfig

from .momo_serializers import MobileMoneyConfigSerializer
from .permissions import require_roles


class MobileMoneyConfigViewSet(viewsets.ModelViewSet):
    queryset = MobileMoneyConfig.objects.all()
    serializer_class = MobileMoneyConfigSerializer
    permission_classes = [require_roles("admin")]

    def get_queryset(self):
        qs = super().get_queryset().filter(tenant=self.request.user.tenant)
        for field in ("provider", "environment"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        """Stub verification. Replace the body with a real provider API call.

        For now, it just checks that the required fields are populated.
        """
        cfg = self.get_object()
        required = ("merchant_code", "api_key", "api_secret")
        missing = [f for f in required if not getattr(cfg, f, "")]
        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing: {', '.join(missing)}"
        else:
            cfg.last_verification_status = "ok"
            cfg.last_verification_message = (
                "All required fields present. "
                "(Provider API not yet wired.)"
            )
        cfg.last_verified_at = timezone.now()
        cfg.save(update_fields=[
            "last_verified_at", "last_verification_status",
            "last_verification_message",
        ])
        return Response(MobileMoneyConfigSerializer(cfg).data)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        cfg = self.get_object()
        if not cfg.is_active:
            return Response(
                {"detail": "Config must be active before it can be the default."},
                status=status.HTTP_409_CONFLICT,
            )
        MobileMoneyConfig.objects.filter(
            tenant=cfg.tenant, is_default=True,
        ).exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default"])
        return Response(MobileMoneyConfigSerializer(cfg).data)
''')

# ─── 10. Register route ────────────────────────────────────────────────
print("==> Patching api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")

if "momo_views" not in u:
    u = u.replace(
        "from .tokens import TenantTokenObtainPairView",
        "from .tokens import TenantTokenObtainPairView\n"
        "from .momo_views import MobileMoneyConfigViewSet",
    )
    u = u.replace(
        'router.register("insurance-claims", InsuranceClaimViewSet, basename="claim")',
        'router.register("insurance-claims", InsuranceClaimViewSet, basename="claim")\n'
        'router.register("mobile-money-configs", MobileMoneyConfigViewSet, basename="momo")',
    )
    up.write_text(u, encoding="utf-8")

# ─── 11. makemigrations ────────────────────────────────────────────────
print("==> makemigrations tenants billing")
sh(PY, "manage.py", "makemigrations", "tenants", "billing")

# ─── 12. RLS migration with explicit dependency ────────────────────────
tenants_migrations = sorted(
    (ROOT / "tenants" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest_tenants = tenants_migrations[-1].stem
print(f"   newest tenants migration: {latest_tenants}")

write("common/migrations/0004_rls_mobile_money.py", f'''\
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "{latest_tenants}"),
        ("common", "0003_rls_billing"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_mobilemoneyconfig"
                    ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_mobilemoneyconfig"
                    FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation
                    ON "tenants_mobilemoneyconfig";
                CREATE POLICY tenant_isolation ON "tenants_mobilemoneyconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation
                    ON "tenants_mobilemoneyconfig";
                ALTER TABLE "tenants_mobilemoneyconfig"
                    DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
''')

# ─── 13. Migrate ───────────────────────────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 14. Extend seed_demo ──────────────────────────────────────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

# a) Import MobileMoneyConfig
if "MobileMoneyConfig" not in seed:
    seed = seed.replace(
        "from tenants.models import Tenant, TenantSequence, TenantSettings, User",
        "from tenants.models import (\n"
        "    MobileMoneyConfig, Tenant, TenantSequence, TenantSettings, User,\n"
        ")",
    )

# b) Add to reset deletion order (before billing Payment)
if "MobileMoneyConfig" not in seed.split("order_of_deletion")[1].split("]")[0]:
    seed = seed.replace(
        "        InsuranceClaim, Payment, InvoiceItem, Invoice,\n"
        "        PatientInsurance, InsuranceProvider,",
        "        InsuranceClaim, Payment, InvoiceItem, Invoice,\n"
        "        PatientInsurance, InsuranceProvider,\n"
        "        MobileMoneyConfig,",
    )

# c) Insert sample configs inside _seed_demo, right after TenantSettings.get_or_create
old_marker = '''        with db_tenant_context(tenant):
            TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"},
            )
            users = self._demo_users(tenant)'''

new_marker = '''        with db_tenant_context(tenant):
            TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW",
                          "enable_mobile_money": True},
            )
            _seed_momo(tenant)
            users = self._demo_users(tenant)'''

if old_marker in seed:
    seed = seed.replace(old_marker, new_marker)

# d) Add the helper function before `class Command`
helper = '''def _seed_momo(tenant):
    """Two sample mobile-money configs (sandbox, credentials pre-filled)."""
    MobileMoneyConfig.objects.get_or_create(
        tenant=tenant, provider="mtn_momo", environment="sandbox",
        defaults=dict(
            display_name="MTN Sandbox",
            merchant_code="MTN-DEMO-001",
            short_code="15001",
            api_key="sandbox-mtn-api-key",
            api_secret="sandbox-mtn-api-secret",
            api_password="sandbox-mtn-api-password",
            subscription_key="sandbox-mtn-subkey",
            callback_url="https://demo.example/hooks/mtn/",
            is_active=True,
            is_default=True,
        ),
    )
    MobileMoneyConfig.objects.get_or_create(
        tenant=tenant, provider="airtel_money", environment="sandbox",
        defaults=dict(
            display_name="Airtel Sandbox",
            merchant_code="AIRTEL-DEMO-001",
            short_code="20002",
            api_key="sandbox-airtel-key",
            api_secret="sandbox-airtel-secret",
            callback_url="https://demo.example/hooks/airtel/",
            is_active=True,
            is_default=False,
        ),
    )


'''
if "def _seed_momo" not in seed:
    seed = seed.replace("class Command(BaseCommand):", helper + "class Command(BaseCommand):")

seed_path.write_text(seed, encoding="utf-8")
print("   patched seed_demo.py")

# ─── 15. Reseed ────────────────────────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")