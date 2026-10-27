#!/usr/bin/env python3
"""
extend_seed.py -- replace seed_demo with a richer, multi-tenant dataset.

Fixes:
  * _reset_tenant now runs inside db_tenant_context() so RLS lets it see
    and delete the rows.
  * AuditLog is deleted first (it has on_delete=PROTECT on Tenant).
"""
from __future__ import annotations

import os
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


write("tenants/management/commands/seed_demo.py", '''\
"""
seed_demo -- populate the OPD with a realistic multi-tenant dataset.

Idempotent: re-running on an already-seeded DB is a no-op.
Use --reset to wipe tenant-scoped data and rebuild from scratch.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand

from audit.models import AuditLog
from clinical.models import ClinicalNote, Order, OrderItem
from common.context import db_tenant_context
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import Tenant, TenantSequence, User
from visits.models import Visit
from vitals.models import Vitals, VitalDefinition, VitalValue


DEMO_PASSWORD = "demo"


# ── helpers ────────────────────────────────────────────────────────────
def _make_user(tenant, email, role, first, last, *, staff=False, superuser=False):
    user, created = User.objects.get_or_create(
        email=email,
        defaults=dict(
            tenant=tenant, role=role,
            first_name=first, last_name=last,
            is_staff=staff, is_superuser=superuser,
        ),
    )
    if created:
        user.set_password(DEMO_PASSWORD)
        user.save()
    return user


def _reset_tenant(tenant):
    """Delete every tenant-scoped row for this tenant in FK-safe order.

    Must run inside db_tenant_context so RLS lets the DELETEs see the rows.
    """
    order_of_deletion = [
        AuditLog,
        StockMovement, Stock,
        PharmacyItem, PharmacyOrder,
        LabResult, LabOrder, RadiologyOrder,
        OrderItem, Order,
        ClinicalNote,
        VitalValue, Vitals, VitalDefinition,
        Visit, Patient,
        LabTest, Medicine,
        TenantSequence,
    ]
    with db_tenant_context(tenant):
        for model in order_of_deletion:
            manager = getattr(model, "all_objects", model.objects)
            manager.filter(tenant=tenant).delete()

        User.objects.filter(tenant=tenant).delete()
        tenant.delete()


# ── command ────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Seed a realistic multi-tenant OPD dataset."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Wipe tenant-scoped data and reseed.")

    def handle(self, *args, **opts):
        if opts["reset"]:
            self.stdout.write(self.style.WARNING("Resetting existing data..."))
            for code in ("demo", "clinic-b"):
                t = Tenant.objects.filter(code=code).first()
                if t:
                    _reset_tenant(t)
            self.stdout.write("   reset complete")

        self._seed_demo()
        self._seed_clinic_b()

        self.stdout.write(self.style.SUCCESS("\\nSeed complete."))
        self.stdout.write("Logins (password = demo):")
        for email in (
            "admin@demo.local", "nurse@demo.local", "doctor@demo.local",
            "lab@demo.local", "radiology@demo.local", "pharmacy@demo.local",
            "admin@clinic-b.local", "doctor@clinic-b.local",
        ):
            self.stdout.write(f"   {email}")

    # ── tenant A ───────────────────────────────────────────────────────
    def _seed_demo(self):
        tenant, _ = Tenant.objects.get_or_create(
            code="demo", defaults={"name": "Demo Clinic"})

        with db_tenant_context(tenant):
            users = self._demo_users(tenant)
            if Visit.all_objects.filter(tenant=tenant).exists():
                self.stdout.write("   [demo] already has visits, skipping")
                return
            catalog = self._demo_catalog(tenant)
            self._demo_clinical(tenant, users, catalog)

        self.stdout.write(self.style.SUCCESS("   [demo] seeded"))

    def _demo_users(self, tenant):
        return {
            "admin":     _make_user(tenant, "admin@demo.local", "admin",
                                    "Demo", "Admin", staff=True, superuser=True),
            "nurse":     _make_user(tenant, "nurse@demo.local", "nurse",
                                    "Nancy", "Nurse", staff=True),
            "doctor":    _make_user(tenant, "doctor@demo.local", "doctor",
                                    "David", "Doctor", staff=True),
            "lab":       _make_user(tenant, "lab@demo.local", "lab",
                                    "Lucy", "Lab", staff=True),
            "radiology": _make_user(tenant, "radiology@demo.local", "radiology",
                                    "Rita", "Radiologist", staff=True),
            "pharmacy":  _make_user(tenant, "pharmacy@demo.local", "pharmacist",
                                    "Peter", "Pharmacist", staff=True),
        }

    def _demo_catalog(self, tenant):
        labs = {}
        for code, name, specimen, unit, lo, hi in [
            ("CBC", "Complete Blood Count", "blood", "10^9/L", 4.0, 11.0),
            ("FBS", "Fasting Blood Sugar", "blood", "mmol/L", 3.9, 5.5),
            ("LFT", "Liver Function Test", "blood", "U/L", 7.0, 56.0),
        ]:
            t, _ = LabTest.objects.get_or_create(
                tenant=tenant, code=code,
                defaults=dict(name=name, specimen_type=specimen,
                              unit=unit, ref_low=lo, ref_high=hi),
            )
            labs[code] = t

        meds = {}
        for code, name, form, strength in [
            ("PARA500", "Paracetamol", "tablet", "500 mg"),
            ("AMOX500", "Amoxicillin", "capsule", "500 mg"),
            ("ORS", "Oral Rehydration Salts", "sachet", "20.5 g"),
        ]:
            m, _ = Medicine.objects.get_or_create(
                tenant=tenant, code=code,
                defaults=dict(name=name, form=form, strength=strength),
            )
            meds[code] = m

        for med_code, batch, qty, expiry in [
            ("PARA500", "PARA-A1", 500, date(2027, 6, 30)),
            ("AMOX500", "AMOX-A1", 200, date(2026, 12, 31)),
            ("ORS",     "ORS-A1",  100, date(2028, 1, 1)),
        ]:
            Stock.objects.update_or_create(
                tenant=tenant, medicine=meds[med_code], batch_no=batch,
                defaults=dict(expiry_date=expiry, quantity=qty),
            )
        return {"labs": labs, "meds": meds}

    def _demo_clinical(self, tenant, users, catalog):
        now = datetime.now(tz=dt_timezone.utc)

        john = Patient.objects.create(
            first_name="John", last_name="Doe", sex="M",
            dob=date(1980, 1, 1), phone="+260-900-000",
        )
        jane = Patient.objects.create(
            first_name="Jane", last_name="Phiri", sex="F",
            dob=date(1992, 5, 12), phone="+260-911-111",
        )

        # ── Visit 1: John, fully completed ────────────────────────────
        v1 = Visit.objects.create(
            patient=john, visit_type=Visit.Type.OPD,
            status=Visit.Status.CLOSED, attending_doctor=users["doctor"],
        )
        Visit.all_objects.filter(pk=v1.pk).update(
            arrived_at=now - timedelta(hours=3),
            closed_at=now - timedelta(hours=2),
        )

        Vitals.objects.create(
            visit=v1, recorded_by=users["nurse"],
            temperature_c=37.2, weight_kg=72.5,
            systolic=120, diastolic=80, pulse=72, spo2=98,
        )
        ClinicalNote.objects.create(
            visit=v1, doctor=users["doctor"],
            subjective="Headache x 3 days",
            objective="BP 120/80, afebrile",
            assessment="Tension headache",
            plan="Analgesia, rest, CBC, chest X-ray",
        )

        lab_o = Order.objects.create(
            visit=v1, ordered_by=users["doctor"],
            kind=Order.Kind.LAB, status=Order.Status.COMPLETED,
        )
        OrderItem.objects.create(order=lab_o, code="CBC",
                                 description="Complete Blood Count")
        lo = LabOrder.objects.create(
            visit=v1, order=lab_o, test=catalog["labs"]["CBC"],
            status=LabOrder.Status.COMPLETED,
            collected_by=users["lab"],
            completed_at=now - timedelta(hours=2, minutes=30),
        )
        LabResult.objects.create(
            lab_order=lo, value_text="7.5", unit="10^9/L",
            flag=LabResult.Flag.NORMAL, resulted_by=users["lab"],
        )

        rad_o = Order.objects.create(
            visit=v1, ordered_by=users["doctor"],
            kind=Order.Kind.RADIOLOGY, status=Order.Status.COMPLETED,
        )
        OrderItem.objects.create(order=rad_o, code="CXR-PA",
                                 description="Chest X-ray PA")
        RadiologyOrder.objects.create(
            visit=v1, order=rad_o,
            modality=RadiologyOrder.Modality.XRAY, body_part="Chest",
            status=RadiologyOrder.Status.REPORTED,
            performed_by=users["radiology"],
            performed_at=now - timedelta(hours=2, minutes=40),
            radiologist=users["radiology"],
            findings="Lung fields clear. No focal consolidation. "
                     "Cardiothoracic ratio within normal limits.",
            impression="Normal chest radiograph.",
            report_url="https://example.invalid/reports/CXR-PA-v1.pdf",
            reported_at=now - timedelta(hours=2),
        )

        rx_o = Order.objects.create(
            visit=v1, ordered_by=users["doctor"],
            kind=Order.Kind.PHARMACY, status=Order.Status.COMPLETED,
        )
        OrderItem.objects.create(order=rx_o, code="PARA500",
                                 description="Paracetamol 500 mg tab")
        po = PharmacyOrder.objects.create(
            visit=v1, order=rx_o,
            status=PharmacyOrder.Status.DISPENSED,
            dispensed_by=users["pharmacy"],
            dispensed_at=now - timedelta(hours=2, minutes=10),
        )
        PharmacyItem.objects.create(
            pharmacy_order=po, medicine=catalog["meds"]["PARA500"],
            dose="1 tab", frequency="TID", duration_days=3,
            route="PO", quantity_prescribed=9, quantity_dispensed=9,
            batch_no="PARA-A1",
        )
        StockMovement.objects.create(
            medicine=catalog["meds"]["PARA500"], batch_no="PARA-A1",
            change_qty=-9, reason="dispense",
            ref_id=po.id, created_by=users["pharmacy"],
        )

        # ── Visit 2: Jane, in consultation with pending orders ───────
        v2 = Visit.objects.create(
            patient=jane, visit_type=Visit.Type.OPD,
            status=Visit.Status.IN_CONSULTATION,
            attending_doctor=users["doctor"],
        )
        Vitals.objects.create(
            visit=v2, recorded_by=users["nurse"],
            temperature_c=38.5, weight_kg=58.0,
            systolic=110, diastolic=70, pulse=96, spo2=97,
        )
        ClinicalNote.objects.create(
            visit=v2, doctor=users["doctor"],
            subjective="Fever, sore throat x 2 days",
            objective="Temp 38.5, pharynx erythematous, no exudate",
            assessment="Likely viral pharyngitis",
            plan="CBC, FBS, CXR, amoxicillin if bacterial",
        )

        lab_o2 = Order.objects.create(
            visit=v2, ordered_by=users["doctor"],
            kind=Order.Kind.LAB, status=Order.Status.PENDING,
        )
        OrderItem.objects.create(order=lab_o2, code="FBS",
                                 description="Fasting Blood Sugar")
        LabOrder.objects.create(
            visit=v2, order=lab_o2, test=catalog["labs"]["FBS"],
            status=LabOrder.Status.PENDING,
        )

        rad_o2 = Order.objects.create(
            visit=v2, ordered_by=users["doctor"],
            kind=Order.Kind.RADIOLOGY, status=Order.Status.PENDING,
        )
        OrderItem.objects.create(order=rad_o2, code="CXR-PA",
                                 description="Chest X-ray PA")
        RadiologyOrder.objects.create(
            visit=v2, order=rad_o2,
            modality=RadiologyOrder.Modality.XRAY, body_part="Chest",
            status=RadiologyOrder.Status.PENDING,
        )

        rx_o2 = Order.objects.create(
            visit=v2, ordered_by=users["doctor"],
            kind=Order.Kind.PHARMACY, status=Order.Status.PENDING,
        )
        OrderItem.objects.create(order=rx_o2, code="AMOX500",
                                 description="Amoxicillin 500 mg cap")
        po2 = PharmacyOrder.objects.create(
            visit=v2, order=rx_o2, status=PharmacyOrder.Status.PENDING,
        )
        PharmacyItem.objects.create(
            pharmacy_order=po2, medicine=catalog["meds"]["AMOX500"],
            dose="1 cap", frequency="TID", duration_days=7,
            route="PO", quantity_prescribed=21, quantity_dispensed=0,
        )

        # ── Visit 3: John, closed with a cancelled order ─────────────
        v3 = Visit.objects.create(
            patient=john, visit_type=Visit.Type.OPD,
            status=Visit.Status.CLOSED, attending_doctor=users["doctor"],
        )
        Visit.all_objects.filter(pk=v3.pk).update(
            arrived_at=now - timedelta(days=1, hours=1),
            closed_at=now - timedelta(days=1),
        )
        Vitals.objects.create(
            visit=v3, recorded_by=users["nurse"],
            temperature_c=36.8, weight_kg=72.6,
            systolic=118, diastolic=78, pulse=70, spo2=99,
        )
        ClinicalNote.objects.create(
            visit=v3, doctor=users["doctor"],
            subjective="Follow-up of headaches",
            objective="No acute distress",
            assessment="Improved",
            plan="No tests needed",
        )
        cancelled = Order.objects.create(
            visit=v3, ordered_by=users["doctor"],
            kind=Order.Kind.LAB, status=Order.Status.CANCELLED,
            notes="Patient declined CBC",
        )
        OrderItem.objects.create(order=cancelled, code="CBC",
                                 description="Complete Blood Count")

    # ── tenant B ───────────────────────────────────────────────────────
    def _seed_clinic_b(self):
        tenant, _ = Tenant.objects.get_or_create(
            code="clinic-b", defaults={"name": "Clinic B"})

        with db_tenant_context(tenant):
            _make_user(tenant, "admin@clinic-b.local", "admin",
                       "ClinicB", "Admin", staff=True, superuser=True)
            doctor_b = _make_user(tenant, "doctor@clinic-b.local", "doctor",
                                  "Beatrice", "Banda", staff=True)

            if Visit.all_objects.filter(tenant=tenant).exists():
                self.stdout.write("   [clinic-b] already has visits, skipping")
                return

            mary = Patient.objects.create(
                first_name="Mary", last_name="Banda", sex="F",
                dob=date(1975, 9, 3), phone="+260-955-222",
            )
            Visit.objects.create(
                patient=mary, visit_type=Visit.Type.OPD,
                status=Visit.Status.OPEN, attending_doctor=doctor_b,
            )

        self.stdout.write(self.style.SUCCESS("   [clinic-b] seeded"))
''')

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print()
print("==> Done.")