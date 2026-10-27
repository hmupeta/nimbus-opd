#!/usr/bin/env python3
"""
add_stripe_paypal.py -- add PaymentGatewayConfig for Stripe & PayPal,
                        integrate with Payment, and RLS protect it.
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


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Extend tenants/models.py ───────────────────────────────────────
print("==> Patching tenants/models.py")
tp = ROOT / "tenants" / "models.py"
t = tp.read_text(encoding="utf-8")

if "class PaymentGatewayProvider" not in t:
    t += '''


class PaymentGatewayProvider(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    PAYPAL = "paypal", "PayPal"


class PaymentGatewayConfig(models.Model):
    """Per-tenant configuration for online payment gateways (Stripe, PayPal)."""

    class Environment(models.TextChoices):
        SANDBOX    = "sandbox", "Sandbox"
        PRODUCTION = "production", "Production"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)
    provider = models.CharField(max_length=32, choices=PaymentGatewayProvider.choices)
    environment = models.CharField(
        max_length=16, choices=Environment.choices, default=Environment.SANDBOX)

    # Public identifiers (safe to expose to frontend)
    publishable_key = models.CharField(
        max_length=255, blank=True,
        help_text="Stripe Publishable Key (pk_...) or PayPal Client ID",
    )

    # Encrypted secrets
    secret_key = EncryptedTextField(
        blank=True,
        help_text="Stripe Secret Key (sk_...) or PayPal Client Secret",
    )
    webhook_secret = EncryptedTextField(
        blank=True,
        help_text="Stripe Webhook Signing Secret (whsec_...) or PayPal Webhook ID",
    )

    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)

    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_verification_status = models.CharField(max_length=32, blank=True)
    last_verification_message = models.TextField(blank=True)

    objects = models.Manager()

    class Meta:
        ordering = ["provider", "-is_default"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider", "environment"],
                name="uniq_gateway_per_provider_env",
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_default=True, is_active=True),
                name="uniq_default_gateway_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} ({self.environment})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_default and not self.is_active:
            raise ValidationError("A default gateway config must be active.")

    def secrets_status(self) -> dict:
        return {
            "secret_key": bool(self.secret_key),
            "webhook_secret": bool(self.webhook_secret),
        }
'''
    tp.write_text(t, encoding="utf-8")

# ─── 2. Extend billing/models.py ───────────────────────────────────────
print("==> Patching billing/models.py")
bp = ROOT / "billing" / "models.py"
b = bp.read_text(encoding="utf-8")

if "payment_gateway_config" not in b:
    b = b.replace(
        '    mobile_money_config = models.ForeignKey(\n'
        '        "tenants.MobileMoneyConfig",\n'
        '        on_delete=models.PROTECT,\n'
        '        null=True, blank=True,\n'
        '        related_name="payments",\n'
        '        help_text="Required when method=mobile_money",\n'
        '    )\n',
        '    mobile_money_config = models.ForeignKey(\n'
        '        "tenants.MobileMoneyConfig",\n'
        '        on_delete=models.PROTECT,\n'
        '        null=True, blank=True,\n'
        '        related_name="payments",\n'
        '        help_text="Required when method=mobile_money",\n'
        '    )\n'
        '    payment_gateway_config = models.ForeignKey(\n'
        '        "tenants.PaymentGatewayConfig",\n'
        '        on_delete=models.PROTECT,\n'
        '        null=True, blank=True,\n'
        '        related_name="payments",\n'
        '        help_text="Required when method=card (Stripe/PayPal)",\n'
        '    )\n'
    )
    bp.write_text(b, encoding="utf-8")

# ─── 3. Update admin ───────────────────────────────────────────────────
print("==> Patching admin files")
ap = ROOT / "tenants" / "admin.py"
a = ap.read_text(encoding="utf-8")
if "PaymentGatewayConfigAdmin" not in a:
    a = a.replace(
        "    MobileMoneyConfig, Tenant, TenantSequence, TenantSettings, User,",
        "    MobileMoneyConfig, PaymentGatewayConfig,\n"
        "    Tenant, TenantSequence, TenantSettings, User,"
    )
    a += '''


class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = (
        "provider", "environment", "publishable_key",
        "is_active", "is_default", "last_verified_at",
    )
    list_filter = ("provider", "environment", "is_active", "is_default")
    readonly_fields = (
        "last_verified_at", "last_verification_status", "last_verification_message",
    )
    fieldsets = (
        ("Identity", {"fields": ("tenant", "provider", "environment")}),
        ("Public Keys", {"fields": ("publishable_key",)}),
        ("Encrypted Secrets", {
            "fields": ("secret_key", "webhook_secret"),
            "description": "Values are encrypted with Fernet before storage.",
        }),
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

    def get_form(self, request, obj=None, **kwargs):
        from django import forms
        form = super().get_form(request, obj, **kwargs)
        for name in ("secret_key", "webhook_secret"):
            if name in form.base_fields:
                form.base_fields[name].widget = forms.PasswordInput(render_value=True)
                form.base_fields[name].required = False
        return form

admin.site.register(PaymentGatewayConfig, PaymentGatewayConfigAdmin)
'''
    ap.write_text(a, encoding="utf-8")

bap = ROOT / "billing" / "admin.py"
ba = bap.read_text(encoding="utf-8")
if "payment_gateway_config" not in ba:
    ba = ba.replace(
        'fields = ("amount", "method", "reference", "mobile_money_config",\n'
        '                  "paid_at", "received_by")',
        'fields = ("amount", "method", "reference", "mobile_money_config",\n'
        '                  "payment_gateway_config", "paid_at", "received_by")',
    )
    bap.write_text(ba, encoding="utf-8")

# ─── 4. Update API serializers & views ─────────────────────────────────
print("==> Patching API files")
bs = ROOT / "api" / "billing_serializers.py"
bser = bs.read_text(encoding="utf-8")
if "payment_gateway_config" not in bser:
    bser = bser.replace(
        '        fields = ["id", "invoice", "amount", "method", "reference",\n'
        '                  "mobile_money_config", "paid_at", "received_by", "notes"]',
        '        fields = ["id", "invoice", "amount", "method", "reference",\n'
        '                  "mobile_money_config", "payment_gateway_config",\n'
        '                  "paid_at", "received_by", "notes"]',
    )
    bs.write_text(bser, encoding="utf-8")

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

    def get_secret_key_set(self, obj): return bool(obj.secret_key)
    def get_webhook_secret_set(self, obj): return bool(obj.webhook_secret)

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
''')

write("api/gateway_views.py", '''\
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from tenants.models import PaymentGatewayConfig
from .gateway_serializers import PaymentGatewayConfigSerializer
from .permissions import require_roles


class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):
    queryset = PaymentGatewayConfig.objects.all()
    serializer_class = PaymentGatewayConfigSerializer
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
        cfg = self.get_object()
        missing = []
        if not cfg.publishable_key: missing.append("publishable_key")
        if not cfg.secret_key: missing.append("secret_key")

        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing: {', '.join(missing)}"
        else:
            cfg.last_verification_status = "ok"
            cfg.last_verification_message = "Credentials present. (Gateway API not yet wired.)"
            
        cfg.last_verified_at = timezone.now()
        cfg.save(update_fields=["last_verified_at", "last_verification_status", "last_verification_message"])
        return Response(PaymentGatewayConfigSerializer(cfg).data)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        cfg = self.get_object()
        if not cfg.is_active:
            return Response({"detail": "Config must be active to be default."}, status=status.HTTP_409_CONFLICT)
        PaymentGatewayConfig.objects.filter(tenant=cfg.tenant, is_default=True).exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default"])
        return Response(PaymentGatewayConfigSerializer(cfg).data)
''')

up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "gateway_views" not in u:
    u = u.replace(
        "from .momo_views import MobileMoneyConfigViewSet",
        "from .momo_views import MobileMoneyConfigViewSet\n"
        "from .gateway_views import PaymentGatewayConfigViewSet",
    )
    u = u.replace(
        'router.register("mobile-money-configs", MobileMoneyConfigViewSet, basename="momo")',
        'router.register("mobile-money-configs", MobileMoneyConfigViewSet, basename="momo")\n'
        'router.register("payment-gateway-configs", PaymentGatewayConfigViewSet, basename="gateway")',
    )
    up.write_text(u, encoding="utf-8")

# ─── 5. Migrations ─────────────────────────────────────────────────────
print("==> makemigrations")
sh(PY, "manage.py", "makemigrations", "tenants", "billing")

tenants_migrations = sorted(
    (ROOT / "tenants" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest_tenants = tenants_migrations[-1].stem

write("common/migrations/0005_rls_gateways.py", f'''\
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "{latest_tenants}"),
        ("common", "0004_rls_mobile_money"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_paymentgatewayconfig" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_paymentgatewayconfig" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_paymentgatewayconfig";
                CREATE POLICY tenant_isolation ON "tenants_paymentgatewayconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_paymentgatewayconfig";
                ALTER TABLE "tenants_paymentgatewayconfig" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
''')

print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 6. Extend seed_demo.py ────────────────────────────────────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

if "PaymentGatewayConfig" not in seed:
    seed = seed.replace(
        "    MobileMoneyConfig, Tenant, TenantSequence, TenantSettings, User,",
        "    MobileMoneyConfig, PaymentGatewayConfig,\n"
        "    Tenant, TenantSequence, TenantSettings, User,"
    )
    seed = seed.replace(
        "        MobileMoneyConfig,",
        "        MobileMoneyConfig,\n        PaymentGatewayConfig,"
    )

    helper = '''def _seed_gateways(tenant):
    PaymentGatewayConfig.objects.get_or_create(
        tenant=tenant, provider="stripe", environment="sandbox",
        defaults=dict(
            publishable_key="pk_test_123456789",
            secret_key="sk_test_987654321",
            webhook_secret="whsec_test_abc123",
            is_active=True,
            is_default=True,
        ),
    )
    PaymentGatewayConfig.objects.get_or_create(
        tenant=tenant, provider="paypal", environment="sandbox",
        defaults=dict(
            publishable_key="PAYPAL-CLIENT-ID-123",
            secret_key="PAYPAL-SECRET-KEY-456",
            webhook_secret="PAYPAL-WEBHOOK-789",
            is_active=True,
            is_default=False,
        ),
    )

'''
    if "def _seed_gateways" not in seed:
        seed = seed.replace("def _seed_momo", helper + "def _seed_momo")

    seed = seed.replace("            _seed_momo(tenant)", "            _seed_momo(tenant)\n            _seed_gateways(tenant)")
    
    seed_path.write_text(seed, encoding="utf-8")
    print("   patched seed_demo.py")

# ─── 7. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")