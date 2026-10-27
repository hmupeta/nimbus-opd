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
