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
