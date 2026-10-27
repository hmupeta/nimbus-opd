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
