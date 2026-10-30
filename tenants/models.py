import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from .encrypted_fields import EncryptedTextField


ROLE_CHOICES = [
    ("admin", "Admin"),
    ("receptionist", "Receptionist"),
    ("nurse", "Nurse"),
    ("doctor", "Doctor"),
    ("lab", "Lab Technician"),
    ("radiology", "Radiologist"),
    ("pharmacist", "Pharmacist"),
    ("accountant", "Accountant"),
    ("finance_manager", "Finance Manager"),
]


class Tenant(models.Model):
    """Represents the Organization / Clinic."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=32, unique=True, help_text="Unique short code")
    name = models.CharField(max_length=128)
    legal_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(max_length=64, blank=True)
    
    # Contact Info
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    website = models.URLField(blank=True)
    
    # Address
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=64, blank=True)
    state_province = models.CharField(max_length=64, blank=True)
    country = models.CharField(max_length=64, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    
    logo = models.ImageField(upload_to="tenant_logos/", null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantSettings(models.Model):
    """Per-tenant configuration and feature flags."""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="settings")
    
    timezone = models.CharField(max_length=64, default="UTC")
    currency_code = models.CharField(max_length=3, default="USD")
    date_format = models.CharField(max_length=32, default="YYYY-MM-DD")
    
    # Feature Flags
    enable_lab = models.BooleanField(default=True)
    enable_radiology = models.BooleanField(default=True)
    enable_pharmacy = models.BooleanField(default=True)
    enable_audit_logs = models.BooleanField(default=True)
    enable_mobile_money = models.BooleanField(default=False)
    
    # Invoice / Receipt Settings
    invoice_prefix = models.CharField(max_length=16, default="INV")
    receipt_footer_text = models.TextField(blank=True)

    def __str__(self):
        return f"Settings for {self.tenant.name}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser must have is_staff and is_superuser True")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT,
        null=True, blank=True, related_name="users",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, blank=True)
    is_platform_admin = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.email


class TenantSequence(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    scope = models.CharField(max_length=32)
    last = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "scope"], name="uniq_tenant_scope"),
        ]



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
    api_user = models.CharField(max_length=128, blank=True, help_text="API User ID generated by provider")
    callback_host = models.CharField(max_length=255, blank=True, help_text="Your server's callback URL")
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



class SmsProvider(models.TextChoices):
    AFRICAS_TALKING = "africas_talking", "Africa's Talking"
    TWILIO          = "twilio", "Twilio"
    OTHER           = "other", "Other"


class SmsConfig(models.Model):
    """Per-tenant SMS gateway configuration."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)
    provider = models.CharField(
        max_length=32, choices=SmsProvider.choices,
        default=SmsProvider.AFRICAS_TALKING,
    )
    sender_id = models.CharField(
        max_length=32, blank=True,
        help_text="The short code or alphanumeric sender ID shown on the patient's phone",
    )

    # Encrypted secrets
    api_key = EncryptedTextField(blank=True)
    api_secret = EncryptedTextField(blank=True)

    is_active = models.BooleanField(default=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_verification_status = models.CharField(max_length=32, blank=True)
    last_verification_message = models.TextField(blank=True)

    objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider"],
                name="uniq_sms_provider_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} ({self.sender_id or 'No Sender ID'})"

    def secrets_status(self) -> dict:
        return {
            "api_key": bool(self.api_key),
            "api_secret": bool(self.api_secret),
        }
