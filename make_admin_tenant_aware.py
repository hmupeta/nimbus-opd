#!/usr/bin/env python3
"""
make_admin_tenant_aware.py -- Strictly isolate Django Admin by tenant.
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


# ─── 1. Fix common/admin.py ────────────────────────────────────────────
print("==> Patching common/admin.py")
write("common/admin.py", '''\
from django.contrib import admin
from .context import get_current_tenant


class TenantModelAdmin(admin.ModelAdmin):
    """Strictly tenant-scoped ModelAdmin.
    
    Even if is_superuser is True (which grants full Django permissions),
    they will ONLY see data for their own tenant.
    Only is_platform_admin=True bypasses the filter.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request.user, "is_platform_admin", False):
            return qs
            
        tenant = get_current_tenant() or getattr(request.user, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs.none()

    def save_model(self, request, obj, form, change):
        if not getattr(obj, "tenant_id", None):
            tenant = get_current_tenant() or getattr(request.user, "tenant", None)
            if tenant is not None:
                obj.tenant = tenant
        super().save_model(request, obj, form, change)
''')

# ─── 2. Fix tenants/admin.py ───────────────────────────────────────────
print("==> Patching tenants/admin.py")
ap = ROOT / "tenants" / "admin.py"
a = ap.read_text(encoding="utf-8")

# Patch TenantAdmin
a = a.replace(
    '''    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_platform_admin or request.user.is_superuser:
            return qs
        t = get_current_tenant() or getattr(request.user, "tenant", None)
        return qs.filter(tenant=t) if t else qs.none()

    def save_model(self, request, obj, form, change):
        if not obj.tenant_id:
            t = get_current_tenant() or getattr(request.user, "tenant", None)
            if t:
                obj.tenant = t
        super().save_model(request, obj, form, change)''',
    '''    def has_module_permission(self, request):
        return True

    def has_view_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return True''', 1
)

# Better: rewrite the whole file for cleanliness
write("tenants/admin.py", '''\
from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from common.context import get_current_tenant
from common.admin import TenantModelAdmin
from .models import (
    MobileMoneyConfig, PaymentGatewayConfig, SmsConfig,
    Tenant, TenantSequence, TenantSettings, User,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "country", "is_active", "created_at")
    list_filter = ("is_active", "country")
    search_fields = ("code", "name", "email")
    readonly_fields = ("id", "created_at")
    
    fieldsets = (
        ("Identity", {"fields": ("id", "code", "name", "legal_name", "registration_number", "is_active")}),
        ("Contact", {"fields": ("email", "phone", "website")}),
        ("Address", {"fields": ("address_line_1", "address_line_2", "city", "state_province", "country", "postal_code")}),
        ("Branding", {"fields": ("logo",)}),
        ("Meta", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request.user, "is_platform_admin", False):
            return qs
        return qs.filter(id=request.user.tenant_id)

    def has_add_permission(self, request):
        # Only platform admins can create new clinics
        return getattr(request.user, "is_platform_admin", False)

    def has_delete_permission(self, request, obj=None):
        return getattr(request.user, "is_platform_admin", False)


class TenantSettingsInline(admin.StackedInline):
    model = TenantSettings
    can_delete = False
    extra = 1


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
        ("Tenant info", {"fields": ("tenant", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff",
                                    "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2",
                       "tenant", "role", "is_staff"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if getattr(request.user, "is_platform_admin", False):
            return qs
        tenant = get_current_tenant() or getattr(request.user, "tenant", None)
        return qs.filter(tenant=tenant) if tenant else qs.none()

    def save_model(self, request, obj, form, change):
        if not getattr(obj, "tenant_id", None):
            tenant = get_current_tenant() or getattr(request.user, "tenant", None)
            if tenant:
                obj.tenant = tenant
        if not getattr(request.user, "is_platform_admin", False):
            obj.is_platform_admin = False  # Prevent privilege escalation
        super().save_model(request, obj, form, change)


@admin.register(TenantSequence)
class TenantSequenceAdmin(TenantModelAdmin):
    list_display = ("tenant", "scope", "last")
    list_filter = ("scope",)


class PasswordFormMixin:
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name in ("api_key", "api_secret", "api_password", "subscription_key",
                     "secret_key", "webhook_secret"):
            if name in form.base_fields:
                form.base_fields[name].widget = forms.PasswordInput(render_value=True)
                form.base_fields[name].required = False
        return form


@admin.register(MobileMoneyConfig)
class MobileMoneyConfigAdmin(PasswordFormMixin, TenantModelAdmin):
    list_display = ("provider", "display_name", "environment", "merchant_code",
                    "is_active", "is_default")
    list_filter = ("provider", "environment", "is_active", "is_default")


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(PasswordFormMixin, TenantModelAdmin):
    list_display = ("provider", "environment", "publishable_key",
                    "is_active", "is_default")
    list_filter = ("provider", "environment", "is_active", "is_default")


@admin.register(SmsConfig)
class SmsConfigAdmin(PasswordFormMixin, TenantModelAdmin):
    list_display = ("provider", "sender_id", "is_active")
    list_filter = ("provider", "is_active")
''')

# ─── 3. Update Seed Script to add clinic_admin@demo.local ──────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

old_admin = '''            "admin":     _make_user(tenant, "admin@demo.local", "admin",
                                    "Demo", "Admin", staff=True, superuser=True),'''
new_admin = '''            "admin":     _make_user(tenant, "admin@demo.local", "admin",
                                    "Demo", "Admin", staff=True, superuser=True),
            "clinic_admin": _make_user(tenant, "clinic_admin@demo.local", "admin",
                                    "Clinic", "Manager", staff=True, superuser=True),'''

if old_admin in seed:
    seed = seed.replace(old_admin, new_admin)
    seed_path.write_text(seed, encoding="utf-8")
    print("   patched seed_demo.py")

# ─── 4. Apply migrations (none needed) and Reseed ──────────────────────
print("==> seed_demo --reset (NO_REDIS=1)")
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
subprocess.run([str(PY), "manage.py", "seed_demo", "--reset"], check=True, env=seed_env)

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")