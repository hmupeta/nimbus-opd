from django.contrib import admin
from common.admin import TenantModelAdmin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(TenantModelAdmin):
    list_display = ("scheduled_start", "patient", "doctor", "status")
    list_filter = ("status", "doctor")
    search_fields = ("patient__first_name", "patient__last_name", "reason")
    autocomplete_fields = ("patient", "doctor")
    readonly_fields = ("created_at", "visit")
    date_hierarchy = "scheduled_start"
