#!/usr/bin/env python3
"""
extend_patient_model.py -- richer patient registration (NRC, guardian, address, etc.)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Rewrite patients/models.py ─────────────────────────────────────
write("patients/models.py", '''\
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
''')

# ─── 2. Rewrite patients/admin.py ──────────────────────────────────────
write("patients/admin.py", '''\
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
''')

# ─── 3. Replace PatientSerializer in api/serializers.py ────────────────
print("==> Patching api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

old_patient_serializer = '''class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "mrn", "first_name", "last_name", "full_name",
                  "dob", "sex", "phone", "email", "address",
                  "national_id", "created_at"]
        read_only_fields = ["id", "mrn", "created_at"]'''

new_patient_serializer = '''class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    age = serializers.SerializerMethodField()
    is_minor = serializers.BooleanField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            # identity
            "id", "mrn", "first_name", "last_name", "full_name",
            "dob", "sex", "age", "is_minor",
            # identification
            "national_id", "passport_number", "nhima_number",
            # contact
            "phone", "alternative_phone", "email",
            # address
            "address", "province", "district", "city_town",
            "compound_village", "street_address", "postal_code",
            # guardian
            "guardian_name", "guardian_relationship",
            "guardian_phone", "guardian_nrc", "guardian_address",
            # demographics
            "marital_status", "occupation",
            # clinical
            "blood_group", "allergies", "chronic_conditions",
            # meta
            "created_at",
        ]
        read_only_fields = ["id", "mrn", "created_at", "age", "is_minor"]

    def get_age(self, obj) -> int | None:
        return obj.age

    def validate(self, data):
        # Cross-field validation for minors
        instance = self.instance
        dob = data.get("dob", getattr(instance, "dob", None))
        guardian_name = data.get("guardian_name",
                                 getattr(instance, "guardian_name", ""))
        guardian_phone = data.get("guardian_phone",
                                  getattr(instance, "guardian_phone", ""))

        if dob:
            from datetime import date
            today = date.today()
            age = (
                today.year - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )
            if age < 18:
                if not guardian_name:
                    raise serializers.ValidationError({
                        "guardian_name":
                            "Parent/guardian name is required for patients under 18."
                    })
                if not guardian_phone:
                    raise serializers.ValidationError({
                        "guardian_phone":
                            "Parent/guardian phone is required for patients under 18."
                    })
        return data'''

if old_patient_serializer in s:
    s = s.replace(old_patient_serializer, new_patient_serializer)
    sp.write_text(s, encoding="utf-8")
    print("   patched PatientSerializer")
else:
    print("   [WARN] PatientSerializer not found verbatim — inspect by hand")

# ─── 4. Expand search fields in PatientViewSet ─────────────────────────
print("==> Patching api/views.py (search)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_search = '''    def get_queryset(self):
        qs = Patient.objects.all()
        q = self.request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(mrn__icontains=q)
            )
        return qs'''

new_search = '''    def get_queryset(self):
        qs = Patient.objects.all()
        q = self.request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(mrn__icontains=q) |
                Q(phone__icontains=q) |
                Q(alternative_phone__icontains=q) |
                Q(national_id__icontains=q) |
                Q(passport_number__icontains=q) |
                Q(nhima_number__icontains=q) |
                Q(guardian_name__icontains=q) |
                Q(guardian_phone__icontains=q)
            )
        return qs'''

if old_search in v:
    v = v.replace(old_search, new_search)
    vp.write_text(v, encoding="utf-8")
    print("   patched PatientViewSet search")
else:
    print("   [WARN] search block not found verbatim")

# ─── 5. Migration + apply ──────────────────────────────────────────────
print("==> makemigrations patients")
sh(PY, "manage.py", "makemigrations", "patients")
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 6. Enrich seed_demo ───────────────────────────────────────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

# 6a. John Doe
old_john = '''        john = Patient.objects.create(
            first_name="John", last_name="Doe", sex="M",
            dob=date(1980, 1, 1), phone="+260-900-000",
        )'''
new_john = '''        john = Patient.objects.create(
            first_name="John", last_name="Doe", sex="M",
            dob=date(1980, 1, 1),
            phone="+260-900-000", alternative_phone="+260-900-001",
            email="john.doe@example.com",
            national_id="123456/78/1",
            nhima_number="NHIMA-00012345",
            province="lusaka", district="Lusaka", city_town="Lusaka",
            compound_village="Matero", street_address="Plot 12, Matero",
            marital_status="married", occupation="Teacher",
            blood_group="O+", allergies="None known",
        )'''
if old_john in seed:
    seed = seed.replace(old_john, new_john)

# 6b. Jane Phiri
old_jane = '''        jane = Patient.objects.create(
            first_name="Jane", last_name="Phiri", sex="F",
            dob=date(1992, 5, 12), phone="+260-911-111",
        )'''
new_jane = '''        jane = Patient.objects.create(
            first_name="Jane", last_name="Phiri", sex="F",
            dob=date(1992, 5, 12), phone="+260-911-111",
            national_id="234567/89/2",
            nhima_number="NHIMA-00067890",
            province="copperbelt", district="Ndola", city_town="Ndola",
            compound_village="Kansenshi",
            marital_status="single", occupation="Nurse",
            blood_group="A+", allergies="Penicillin",
        )'''
if old_jane in seed:
    seed = seed.replace(old_jane, new_jane)

# 6c. Add a minor patient (with guardian) right after Jane
old_marker = '''        # Visit 1: John, fully completed'''
minor_block = '''        # A pediatric patient — demonstrates the required-guardian flow
        aisha = Patient.objects.create(
            first_name="Aisha", last_name="Zulu", sex="F",
            dob=date.today().replace(year=date.today().year - 5),
            province="lusaka", district="Lusaka", city_town="Lusaka",
            compound_village="Kalingalinga",
            guardian_name="Grace Zulu",
            guardian_relationship="Mother",
            guardian_phone="+260-977-334-455",
            guardian_nrc="345678/90/4",
            guardian_address="House 45, Kalingalinga, Lusaka",
            blood_group="O+",
        )

        # Visit 1: John, fully completed'''
if old_marker in seed and "Aisha" not in seed:
    seed = seed.replace(old_marker, minor_block, 1)

# 6d. Mary Banda (clinic-b)
old_mary = '''            mary = Patient.objects.create(
                first_name="Mary", last_name="Banda", sex="F",
                dob=date(1975, 9, 3), phone="+260-955-222",
            )'''
new_mary = '''            mary = Patient.objects.create(
                first_name="Mary", last_name="Banda", sex="F",
                dob=date(1975, 9, 3), phone="+260-955-222",
                national_id="456789/01/5",
                nhima_number="NHIMA-00099988",
                province="lusaka", district="Lusaka", city_town="Lusaka",
                compound_village="Kabwata",
                marital_status="married", occupation="Accountant",
                blood_group="B+",
            )'''
if old_mary in seed:
    seed = seed.replace(old_mary, new_mary)

seed_path.write_text(seed, encoding="utf-8")
print("   patched seed_demo.py")

# ─── 7. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")