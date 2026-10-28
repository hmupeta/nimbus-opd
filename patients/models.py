from datetime import date

from django.core.exceptions import ValidationError
from django.db import models, transaction

from common.context import get_current_tenant
from common.models import TenantAwareModel
from tenants.models import TenantSequence


def next_sequence(tenant, scope: str) -> int:
    with transaction.atomic():
        seq, _ = TenantSequence.objects.select_for_update().get_or_create(
            tenant=tenant, scope=scope,
        )
        seq.last += 1
        seq.save(update_fields=["last"])
        return seq.last

class Patient(TenantAwareModel):
    SEX_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]

    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
        ("other", "Other"),
    ]

    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"), ("A-", "A-"),
        ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"),
        ("O+", "O+"), ("O-", "O-"),
    ]

    ZAMBIAN_PROVINCES = [
        ("central", "Central"),
        ("copperbelt", "Copperbelt"),
        ("eastern", "Eastern"),
        ("luapula", "Luapula"),
        ("lusaka", "Lusaka"),
        ("muchinga", "Muchinga"),
        ("northern", "Northern"),
        ("north_western", "North-Western"),
        ("southern", "Southern"),
        ("western", "Western"),
    ]

    # ── Identity ────────────────────────────────────────────────────────
    mrn = models.CharField(max_length=32, blank=True, db_index=True)
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    dob = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, blank=True)

    national_id = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text="NRC (adults) or National ID / Passport of parent (minors)",
    )
    passport_number = models.CharField(max_length=64, blank=True)
    nhima_number = models.CharField(
        max_length=32, blank=True, db_index=True,
        help_text="NHIMA health insurance number, if enrolled",
    )

    # ── Contact ─────────────────────────────────────────────────────────
    phone = models.CharField(max_length=32, blank=True)
    alternative_phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)

    # ── Address ─────────────────────────────────────────────────────────
    address = models.TextField(
        blank=True, help_text="Free-form address (legacy / short notes)")
    province = models.CharField(
        max_length=32, choices=ZAMBIAN_PROVINCES, blank=True)
    district = models.CharField(max_length=64, blank=True)
    city_town = models.CharField(max_length=64, blank=True)
    compound_village = models.CharField(max_length=128, blank=True)
    street_address = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=16, blank=True)

    # ── Parent / Guardian (required for patients under 18) ──────────────
    guardian_name = models.CharField(max_length=128, blank=True)
    guardian_relationship = models.CharField(max_length=32, blank=True,
                                             help_text="Mother, Father, Aunt, etc.")
    guardian_phone = models.CharField(max_length=32, blank=True)
    guardian_nrc = models.CharField(max_length=64, blank=True)
    guardian_address = models.TextField(blank=True)

    # ── Demographics ────────────────────────────────────────────────────
    marital_status = models.CharField(
        max_length=16, choices=MARITAL_STATUS_CHOICES, blank=True)
    occupation = models.CharField(max_length=128, blank=True)

    # ── Clinical snapshot ───────────────────────────────────────────────
    blood_group = models.CharField(
        max_length=4, choices=BLOOD_GROUP_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "mrn"], name="uniq_patient_mrn"),
        ]
        indexes = [
            models.Index(fields=["tenant", "phone"]),
            models.Index(fields=["tenant", "national_id"]),
        ]

    # ── Computed helpers ────────────────────────────────────────────────
    @property
    def age(self) -> int | None:
        if not self.dob:
            return None
        today = date.today()
        return (
            today.year - self.dob.year
            - ((today.month, today.day) < (self.dob.month, self.dob.day))
        )

    @property
    def is_minor(self) -> bool:
        a = self.age
        return a is not None and a < 18

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    # ── Validation ──────────────────────────────────────────────────────
    def clean(self):
        errors = {}
        if self.is_minor:
            if not self.guardian_name:
                errors["guardian_name"] = (
                    "Parent/guardian name is required for patients under 18.")
            if not self.guardian_phone:
                errors["guardian_phone"] = (
                    "Parent/guardian phone is required for patients under 18.")
        if errors:
            raise ValidationError(errors)

    # ── Save ────────────────────────────────────────────────────────────
    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            tenant = get_current_tenant()
            if tenant is not None:
                self.tenant = tenant
        if not self.mrn:
            if self.tenant_id is None:
                raise ValueError("Tenant required to generate MRN")
            self.mrn = f"MRN-{next_sequence(self.tenant, 'mrn'):06d}"
        super().save(*args, **kwargs)
