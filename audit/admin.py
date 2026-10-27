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
