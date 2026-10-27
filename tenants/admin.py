from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from common.context import get_current_tenant
from common.admin import TenantModelAdmin
from .models import (
    MobileMoneyConfig, PaymentGatewayConfig, SmsConfig,
    Tenant, TenantSequence, TenantSettings, User,
)



@admin.action(description="Approve selected clinics (Grant Access)")
def approve_tenants(modeladmin, request, queryset):
    queryset.update(is_active=True)

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "country", "is_active", "created_at")
    actions = [approve_tenants]
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
