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
