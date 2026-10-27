#!/usr/bin/env python3
"""
extend_org_settings.py -- add Organization Profile and Settings to the Tenant.
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


# ─── 1. Install Pillow (required for ImageField) ───────────────────────
print("==> Installing Pillow for logo uploads")
sh(PY, "-m", "pip", "install", "--quiet", "Pillow>=10.0")

# ─── 2. Update tenants/models.py ───────────────────────────────────────
write("tenants/models.py", '''\
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


ROLE_CHOICES = [
    ("admin", "Admin"),
    ("receptionist", "Receptionist"),
    ("nurse", "Nurse"),
    ("doctor", "Doctor"),
    ("lab", "Lab Technician"),
    ("radiology", "Radiologist"),
    ("pharmacist", "Pharmacist"),
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
''')

# ─── 3. Update tenants/admin.py ────────────────────────────────────────
write("tenants/admin.py", '''\
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from common.admin import TenantModelAdmin

from .models import Tenant, TenantSequence, TenantSettings, User


class TenantSettingsInline(admin.StackedInline):
    model = TenantSettings
    can_delete = False
    extra = 1


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "country", "is_active", "created_at")
    list_filter = ("is_active", "country")
    search_fields = ("code", "name", "email")
    readonly_fields = ("id", "created_at")
    inlines = [TenantSettingsInline]
    
    fieldsets = (
        ("Identity", {"fields": ("id", "code", "name", "legal_name", "registration_number", "is_active")}),
        ("Contact", {"fields": ("email", "phone", "website")}),
        ("Address", {"fields": ("address_line_1", "address_line_2", "city", "state_province", "country", "postal_code")}),
        ("Branding", {"fields": ("logo",)}),
        ("Meta", {"fields": ("created_at",)}),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "role",
                    "tenant", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "tenant")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Tenant info", {"fields": ("tenant", "role", "is_platform_admin")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                    "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2",
                       "tenant", "role", "is_staff", "is_superuser"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")


@admin.register(TenantSequence)
class TenantSequenceAdmin(TenantModelAdmin):
    list_display = ("tenant", "scope", "last")
    list_filter = ("scope",)
''')

# ─── 4. Update api/serializers.py to expose settings ───────────────────
# (We just append the new serializers and update TenantSerializer)
print("==> Patching api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

if "class TenantSettingsSerializer" not in s:
    s = s.replace(
        "from tenants.models import Tenant, User",
        "from tenants.models import Tenant, TenantSettings, User"
    )
    s = s.replace(
        '''class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "code", "name", "is_active", "created_at"]
        read_only_fields = fields''',
        '''class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSettings
        exclude = ["tenant"]


class TenantSerializer(serializers.ModelSerializer):
    settings = TenantSettingsSerializer(read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id", "code", "name", "legal_name", "registration_number",
            "email", "phone", "website",
            "address_line_1", "address_line_2", "city", "state_province",
            "country", "postal_code", "logo",
            "is_active", "created_at", "settings",
        ]
        read_only_fields = ["id", "created_at"]'''
    )
    sp.write_text(s, encoding="utf-8")
    print("   patched api/serializers.py")

# ─── 5. Update api/views.py to allow updating settings ─────────────────
print("==> Patching api/views.py")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "update_settings" not in v:
    # Add import
    v = v.replace(
        "from tenants.models import Tenant, User",
        "from tenants.models import Tenant, TenantSettings, User"
    )
    v = v.replace(
        "from .permissions import require_roles",
        "from .permissions import require_roles\nfrom .serializers import TenantSettingsSerializer"
    )
    # Add action to TenantViewSet
    v = v.replace(
        '''    def get_queryset(self):
        u = self.request.user
        if u.is_platform_admin or u.is_superuser:
            return Tenant.objects.all()
        return Tenant.objects.filter(id=u.tenant_id)''',
        '''    def get_queryset(self):
        u = self.request.user
        if u.is_platform_admin or u.is_superuser:
            return Tenant.objects.all()
        return Tenant.objects.filter(id=u.tenant_id)

    @action(detail=True, methods=["patch"], permission_classes=[require_roles("admin")])
    def settings(self, request, code=None):
        tenant = self.get_object()
        # Enforce users can only edit their own tenant's settings unless platform admin
        if not (request.user.is_platform_admin or request.user.is_superuser):
            if request.user.tenant_id != tenant.id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Cannot edit another tenant's settings")
        
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        ser = TenantSettingsSerializer(settings_obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)'''
    )
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")

# ─── 6. Create RLS policy for new TenantSettings table ─────────────────
print("==> Writing RLS migration for TenantSettings")
write("common/migrations/0002_rls_tenant_settings.py", '''\
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_tenantsettings"),
        ("common", "0001_rls_policies"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_tenantsettings" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_tenantsettings" FORCE ROW LEVEL SECURITY;
                CREATE POLICY tenant_isolation ON "tenants_tenantsettings"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_tenantsettings";
                ALTER TABLE "tenants_tenantsettings" DISABLE ROW LEVEL SECURITY;
            """
        )
    ]
''')

# ─── 7. Generate and Apply Migrations ──────────────────────────────────
print("==> makemigrations")
sh(PY, "manage.py", "makemigrations", "tenants")

print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 8. Update Seed Data so new tenants get settings ───────────────────
print("==> Updating seed_demo to create default settings")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")
if "TenantSettings" not in seed:
    seed = seed.replace(
        "from tenants.models import Tenant, TenantSequence, User",
        "from tenants.models import Tenant, TenantSettings, TenantSequence, User"
    )
    # Add settings creation inside _seed_demo and _seed_clinic_b
    seed = seed.replace(
        '''        tenant, _ = Tenant.objects.get_or_create(
            code="demo", defaults={"name": "Demo Clinic"})''',
        '''        tenant, _ = Tenant.objects.get_or_create(
            code="demo", defaults={"name": "Demo Clinic"})
        TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"}
        )'''
    )
    seed = seed.replace(
        '''        tenant, _ = Tenant.objects.get_or_create(
            code="clinic-b", defaults={"name": "Clinic B"})''',
        '''        tenant, _ = Tenant.objects.get_or_create(
            code="clinic-b", defaults={"name": "Clinic B"})
        TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"}
        )'''
    )
    seed_path.write_text(seed, encoding="utf-8")
    print("   patched seed_demo.py")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Refresh /admin/tenants/tenant/ to see the new Organization Profile.")
print("    API: /api/tenants/demo/settings/ (PATCH) to update settings.")