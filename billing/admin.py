from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import (
    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,
    PatientInsurance, Payment,
)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ("category", "description", "quantity", "unit_price",
              "total", "order_item_code")
    readonly_fields = ("total",)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("amount", "method", "reference", "mobile_money_config",
                  "payment_gateway_config", "paid_at", "received_by")
    readonly_fields = ("paid_at",)


class ClaimInline(admin.TabularInline):
    model = InsuranceClaim
    extra = 0
    fields = ("claim_no", "patient_insurance", "amount_claimed",
              "amount_approved", "status", "submitted_at", "decided_at")
    readonly_fields = ("claim_no", "submitted_at", "decided_at")


@admin.register(InsuranceProvider)
class InsuranceProviderAdmin(TenantModelAdmin):
    list_display = ("code", "name", "contact_phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(PatientInsurance)
class PatientInsuranceAdmin(TenantModelAdmin):
    list_display = ("patient", "provider", "policy_number",
                    "is_primary", "is_active", "valid_to")
    list_filter = ("provider", "is_primary", "is_active")
    search_fields = ("patient__first_name", "patient__last_name",
                     "policy_number", "member_id")
    autocomplete_fields = ("patient",)


@admin.register(Invoice)
class InvoiceAdmin(TenantModelAdmin):
    list_display = ("invoice_no", "patient", "status", "total",
                    "balance", "currency", "issued_at")
    list_filter = ("status", "currency")
    search_fields = ("invoice_no", "patient__first_name",
                     "patient__last_name", "visit__visit_no")
    readonly_fields = ("invoice_no", "subtotal", "total", "balance",
                       "created_at")
    autocomplete_fields = ("patient", "visit")
    inlines = [InvoiceItemInline, PaymentInline, ClaimInline]


@admin.register(Payment)
class PaymentAdmin(TenantModelAdmin):
    list_display = ("invoice", "amount", "method", "reference",
                    "mobile_money_config", "paid_at", "received_by")
    list_filter = ("method",)
    search_fields = ("invoice__invoice_no", "reference")
    readonly_fields = ("paid_at",)


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(TenantModelAdmin):
    list_display = ("claim_no", "invoice", "patient_insurance",
                    "amount_claimed", "amount_approved", "status",
                    "submitted_at")
    list_filter = ("status", "patient_insurance__provider")
    search_fields = ("claim_no", "invoice__invoice_no")
    readonly_fields = ("claim_no", "created_at")
