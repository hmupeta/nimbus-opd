from django.contrib import admin

from common.admin import TenantModelAdmin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(TenantModelAdmin):
    list_display = (
        "mrn", "full_name", "sex", "age", "phone",
        "national_id", "province", "is_minor",
    )
    list_filter = ("sex", "province", "blood_group", "marital_status")
    search_fields = (
        "mrn", "first_name", "last_name",
        "phone", "alternative_phone",
        "national_id", "passport_number", "nhima_number",
        "guardian_name", "guardian_phone",
    )
    readonly_fields = ("mrn", "created_at", "age", "is_minor")
    ordering = ("-created_at",)

    fieldsets = (
        ("Identity", {
            "fields": (
                "mrn", "first_name", "last_name", "dob", "sex",
                "age", "is_minor", "created_at",
            ),
        }),
        ("Identification", {
            "fields": ("national_id", "passport_number", "nhima_number"),
        }),
        ("Contact", {
            "fields": ("phone", "alternative_phone", "email"),
        }),
        ("Address", {
            "fields": (
                "province", "district", "city_town",
                "compound_village", "street_address", "postal_code",
                "address",
            ),
        }),
        ("Parent / Guardian (required for under-18)", {
            "fields": (
                "guardian_name", "guardian_relationship",
                "guardian_phone", "guardian_nrc", "guardian_address",
            ),
        }),
        ("Demographics", {
            "fields": ("marital_status", "occupation"),
        }),
        ("Clinical Snapshot", {
            "fields": ("blood_group", "allergies", "chronic_conditions"),
        }),
    )
