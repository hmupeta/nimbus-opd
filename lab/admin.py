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
