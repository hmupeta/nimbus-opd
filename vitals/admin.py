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
