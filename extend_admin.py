#!/usr/bin/env python3
"""
extend_admin.py -- register every model in Django admin, tenant-aware,
                   with inlines for the visit timeline.
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


# ─── 1. shared TenantModelAdmin ────────────────────────────────────────
write("common/admin.py", '''\
from django.contrib import admin

from .context import get_current_tenant


class TenantModelAdmin(admin.ModelAdmin):
    """Tenant-scoped ModelAdmin.

    - Filters the changelist to the current tenant (via context set by
      TenantMiddleware) unless the user is a platform admin / superuser.
    - Auto-assigns tenant on create if not already set.

    NOTE: even for superusers, RLS in PostgreSQL still applies unless the DB
    role has BYPASSRLS. So a platform admin must connect as opd_owner (or a
    role with BYPASSRLS) to see every tenant's rows in the admin.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_platform_admin or request.user.is_superuser:
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


# ─── 2. tenants/admin.py ───────────────────────────────────────────────
write("tenants/admin.py", '''\
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from common.admin import TenantModelAdmin

from .models import Tenant, TenantSequence, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at")


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


# ─── 3. patients/admin.py ──────────────────────────────────────────────
write("patients/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(TenantModelAdmin):
    list_display = ("mrn", "first_name", "last_name", "sex",
                    "dob", "phone", "created_at")
    list_filter = ("sex",)
    search_fields = ("mrn", "first_name", "last_name", "phone", "national_id")
    readonly_fields = ("mrn", "created_at")
    ordering = ("-created_at",)
''')


# ─── 4. visits/admin.py ────────────────────────────────────────────────
write("visits/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin
from clinical.models import ClinicalNote, Order
from lab.models import LabOrder
from pharmacy.models import PharmacyOrder
from radiology.models import RadiologyOrder
from vitals.models import Vitals

from .models import Visit


class VitalsInline(admin.StackedInline):
    model = Vitals
    can_delete = False
    extra = 0


class ClinicalNoteInline(admin.StackedInline):
    model = ClinicalNote
    extra = 0
    fields = ("doctor", "kind", "subjective", "objective",
              "assessment", "plan", "created_at")
    readonly_fields = ("created_at",)


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    fields = ("kind", "status", "priority", "ordered_by", "notes", "created_at")
    readonly_fields = ("created_at",)


class LabOrderInline(admin.TabularInline):
    model = LabOrder
    extra = 0
    fields = ("test", "order", "status", "collected_at", "completed_at")
    readonly_fields = ("collected_at", "completed_at")


class RadiologyOrderInline(admin.TabularInline):
    model = RadiologyOrder
    extra = 0
    fields = ("modality", "body_part", "status", "reported_at")
    readonly_fields = ("reported_at",)


class PharmacyOrderInline(admin.TabularInline):
    model = PharmacyOrder
    extra = 0
    fields = ("order", "status", "dispensed_by", "dispensed_at")
    readonly_fields = ("dispensed_at",)


@admin.register(Visit)
class VisitAdmin(TenantModelAdmin):
    list_display = ("visit_no", "patient", "visit_type", "status",
                    "arrived_at", "attending_doctor")
    list_filter = ("visit_type", "status")
    search_fields = ("visit_no",
                     "patient__first_name", "patient__last_name", "patient__mrn")
    readonly_fields = ("visit_no", "arrived_at", "closed_at")
    autocomplete_fields = ("patient",)
    inlines = [
        VitalsInline, ClinicalNoteInline, OrderInline,
        LabOrderInline, RadiologyOrderInline, PharmacyOrderInline,
    ]
    fieldsets = (
        (None, {"fields": ("visit_no", "patient", "visit_type", "status")}),
        ("Clinical", {"fields": ("attending_doctor",)}),
        ("Timestamps", {"fields": ("arrived_at", "closed_at")}),
    )
''')


# ─── 5. vitals/admin.py ────────────────────────────────────────────────
write("vitals/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import Vitals, VitalDefinition, VitalValue


@admin.register(Vitals)
class VitalsAdmin(TenantModelAdmin):
    list_display = ("visit", "recorded_by", "temperature_c",
                    "systolic", "diastolic", "pulse", "spo2", "recorded_at")
    search_fields = ("visit__visit_no",)


@admin.register(VitalDefinition)
class VitalDefinitionAdmin(TenantModelAdmin):
    list_display = ("code", "label", "unit", "data_type", "is_active")
    list_filter = ("data_type", "is_active")
    search_fields = ("code", "label")


@admin.register(VitalValue)
class VitalValueAdmin(TenantModelAdmin):
    list_display = ("visit", "definition", "value_num", "value_text", "recorded_at")
    search_fields = ("visit__visit_no",)
''')


# ─── 6. clinical/admin.py ──────────────────────────────────────────────
write("clinical/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import ClinicalNote, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(ClinicalNote)
class ClinicalNoteAdmin(TenantModelAdmin):
    list_display = ("visit", "doctor", "kind", "created_at")
    list_filter = ("kind",)
    search_fields = ("visit__visit_no", "doctor__email")
    readonly_fields = ("created_at",)


@admin.register(Order)
class OrderAdmin(TenantModelAdmin):
    list_display = ("id", "visit", "kind", "status", "priority",
                    "ordered_by", "created_at")
    list_filter = ("kind", "status", "priority")
    search_fields = ("visit__visit_no",)
    readonly_fields = ("created_at",)
    inlines = [OrderItemInline]
''')


# ─── 7. lab/admin.py ───────────────────────────────────────────────────
write("lab/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import LabOrder, LabResult, LabTest


class LabResultInline(admin.StackedInline):
    model = LabResult
    extra = 0


@admin.register(LabTest)
class LabTestAdmin(TenantModelAdmin):
    list_display = ("code", "name", "specimen_type", "unit", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(LabOrder)
class LabOrderAdmin(TenantModelAdmin):
    list_display = ("id", "visit", "test", "status",
                    "ordered_at", "completed_at", "collected_by")
    list_filter = ("status",)
    search_fields = ("visit__visit_no",)
    inlines = [LabResultInline]


@admin.register(LabResult)
class LabResultAdmin(TenantModelAdmin):
    list_display = ("lab_order", "value_text", "unit", "flag",
                    "resulted_by", "resulted_at")
    list_filter = ("flag",)
    readonly_fields = ("resulted_at",)
''')


# ─── 8. radiology/admin.py ─────────────────────────────────────────────
write("radiology/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import RadiologyOrder


@admin.register(RadiologyOrder)
class RadiologyOrderAdmin(TenantModelAdmin):
    list_display = ("id", "visit", "modality", "body_part",
                    "status", "reported_at", "radiologist")
    list_filter = ("modality", "status")
    search_fields = ("visit__visit_no",)
    readonly_fields = ("ordered_at", "performed_at", "reported_at")
''')


# ─── 9. pharmacy/admin.py ──────────────────────────────────────────────
write("pharmacy/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement


class PharmacyItemInline(admin.TabularInline):
    model = PharmacyItem
    extra = 0


@admin.register(Medicine)
class MedicineAdmin(TenantModelAdmin):
    list_display = ("code", "name", "form", "strength", "unit", "is_active")
    list_filter = ("is_active", "form")
    search_fields = ("code", "name")


@admin.register(PharmacyOrder)
class PharmacyOrderAdmin(TenantModelAdmin):
    list_display = ("id", "visit", "status",
                    "dispensed_by", "dispensed_at")
    list_filter = ("status",)
    search_fields = ("visit__visit_no",)
    readonly_fields = ("dispensed_at",)
    inlines = [PharmacyItemInline]


@admin.register(Stock)
class StockAdmin(TenantModelAdmin):
    list_display = ("medicine", "batch_no", "expiry_date", "quantity")
    list_filter = ("medicine",)
    search_fields = ("medicine__code", "medicine__name", "batch_no")


@admin.register(StockMovement)
class StockMovementAdmin(TenantModelAdmin):
    list_display = ("medicine", "batch_no", "change_qty",
                    "reason", "created_by", "created_at")
    list_filter = ("reason",)
    readonly_fields = ("created_at",)
    search_fields = ("medicine__code", "medicine__name")
''')


# ─── 10. audit/admin.py ────────────────────────────────────────────────
write("audit/admin.py", '''\
from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(TenantModelAdmin):
    list_display = ("at", "user", "action", "content_type", "object_id")
    list_filter = ("action", "content_type")
    search_fields = ("object_id", "user__email")
    readonly_fields = ("user", "action", "content_type", "object_id",
                       "before", "after", "at", "ip")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
''')


# ─── 11. sanity check ──────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Reload http://127.0.0.1:8000/admin/")
print("    You should now see app groups:")
print("      Tenants     -> Tenants, Users, Tenant sequences")
print("      Patients    -> Patients")
print("      Visits      -> Visits (with inlines for the whole timeline)")
print("      Vitals      -> Vitals, Vital definitions, Vital values")
print("      Clinical    -> Clinical notes, Orders")
print("      Lab         -> Lab tests, Lab orders, Lab results")
print("      Radiology   -> Radiology orders")
print("      Pharmacy    -> Medicines, Pharmacy orders, Stock, Stock movements")
print("      Audit       -> Audit logs")
print()
print("Open 'Visits' -> click V00000001 -> the demo encounter loads")
print("with vitals, SOAP note, lab, radiology, pharmacy all in one page.")