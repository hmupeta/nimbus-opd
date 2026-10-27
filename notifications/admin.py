from django.contrib import admin
from common.admin import TenantModelAdmin
from .models import SmsLog


@admin.register(SmsLog)
class SmsLogAdmin(TenantModelAdmin):
    list_display = ("created_at", "recipient", "status", "provider")
    list_filter = ("status", "provider")
    search_fields = ("recipient", "message")
    readonly_fields = ("created_at", "sent_at")
