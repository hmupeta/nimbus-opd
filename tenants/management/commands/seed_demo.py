"""
seed_demo -- realistic multi-tenant OPD dataset.

Use --reset to wipe tenant-scoped data and rebuild from scratch.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.core.management.base import BaseCommand

from audit.models import AuditLog
from billing.models import (
    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,
    PatientInsurance, Payment,
)
from clinical.models import ClinicalNote, Order, OrderItem
from common.context import db_tenant_context, suspend_audit
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from accounting.models import ChartOfAccount
from notifications.models import SmsLog
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import (
    MobileMoneyConfig, PaymentGatewayConfig,
    Tenant, TenantSequence, TenantSettings, User,
)
from visits.models import Visit
from vitals.models import VitalDefinition, Vitals, VitalValue


DEMO_PASSWORD = "demo"


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
    """Wipe every tenant-scoped row. Audit signals are suspended during
    the reset so we don't generate hundreds of useless AuditLog rows."""
    order_of_deletion = [
        # Billing first — Invoice references Visit and Patient with PROTECT
        InsuranceClaim, Payment, InvoiceItem, Invoice,
        PatientInsurance, InsuranceProvider,
        MobileMoneyConfig,
        PaymentGatewayConfig,
        # Clinical + everything else
        StockMovement, Stock,
        PharmacyItem, PharmacyOrder,
        LabResult, LabOrder, RadiologyOrder,
        OrderItem, Order,
        ClinicalNote,
        VitalValue, Vitals, VitalDefinition,
        Visit, Patient,
        LabTest, Medicine,
        TenantSequence,
        TenantSettings,
        SmsLog,
        AuditLog,
        User,
    ]
    with suspend_audit():
        with db_tenant_context(tenant):
            for model in order_of_deletion:
                manager = getattr(model, "all_objects", model.objects)
                manager.filter(tenant=tenant).delete()
            tenant.delete()


def _seed_gateways(tenant):
    PaymentGatewayConfig.objects.get_or_create(
        tenant=tenant, provider="stripe", environment="sandbox",
        defaults=dict(
            publishable_key="pk_test_123456789",
            secret_key="sk_test_987654321",
            webhook_secret="whsec_test_abc123",
            is_active=True,
            is_default=True,
        ),
    )
    PaymentGatewayConfig.objects.get_or_create(
        tenant=tenant, provider="paypal", environment="sandbox",
        defaults=dict(
            publishable_key="PAYPAL-CLIENT-ID-123",
            secret_key="PAYPAL-SECRET-KEY-456",
            webhook_secret="PAYPAL-WEBHOOK-789",
            is_active=True,
            is_default=False,
        ),
    )

def _seed_momo(tenant):
    """Two sample mobile-money configs (sandbox, credentials pre-filled)."""
    MobileMoneyConfig.objects.get_or_create(
        tenant=tenant, provider="mtn_momo", environment="sandbox",
        defaults=dict(
            display_name="MTN Sandbox",
            merchant_code="MTN-DEMO-001",
            short_code="15001",
            api_key="sandbox-mtn-api-key",
            api_secret="sandbox-mtn-api-secret",
            api_password="sandbox-mtn-api-password",
            subscription_key="sandbox-mtn-subkey",
            callback_url="https://demo.example/hooks/mtn/",
            is_active=True,
            is_default=True,
        ),
    )
    MobileMoneyConfig.objects.get_or_create(
        tenant=tenant, provider="airtel_money", environment="sandbox",
        defaults=dict(
            display_name="Airtel Sandbox",
            merchant_code="AIRTEL-DEMO-001",
            short_code="20002",
            api_key="sandbox-airtel-key",
            api_secret="sandbox-airtel-secret",
            callback_url="https://demo.example/hooks/airtel/",
            is_active=True,
            is_default=False,
        ),
    )


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

        self._ensure_superadmin()
        self._seed_demo()
        self._seed_clinic_b()

        self.stdout.write(self.style.SUCCESS("\nSeed complete."))


    def _seed_demo(self):
        tenant, _ = Tenant.objects.get_or_create(
            code="demo", defaults={"name": "Demo Clinic"})
        with db_tenant_context(tenant):
            TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW",
                          "enable_mobile_money": True},
            )
            _seed_momo(tenant)
            _seed_gateways(tenant)

        # Seed Default Chart of Accounts
        accounts = [
            ("1000", "Cash & Bank", "asset"),
            ("1100", "Accounts Receivable", "asset"),
            ("4000", "Consultation Revenue", "revenue"),
            ("4100", "Pharmacy Revenue", "revenue"),
            ("4200", "Lab Revenue", "revenue"),
            ("4300", "Radiology Revenue", "revenue"),
        ]
        for code, name, type in accounts:
            ChartOfAccount.objects.get_or_create(
                tenant=tenant, code=code, defaults={"name": name, "type": type}
            )

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
            "clinic_admin": _make_user(tenant, "clinic_admin@demo.local", "admin",
                                    "Clinic", "Manager", staff=True, superuser=True),
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
            "accountant": _make_user(tenant, "accountant@demo.local", "accountant",
                                    "Alice", "Accountant", staff=True),
            "finance":    _make_user(tenant, "finance@demo.local", "finance_manager",
                                    "Frank", "Manager", staff=True),
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
            dob=date(1980, 1, 1),
            phone="+260-900-000", alternative_phone="+260-900-001",
            email="john.doe@example.com",
            national_id="123456/78/1",
            nhima_number="NHIMA-00012345",
            province="lusaka", district="Lusaka", city_town="Lusaka",
            compound_village="Matero", street_address="Plot 12, Matero",
            marital_status="married", occupation="Teacher",
            blood_group="O+", allergies="None known",
        )
        jane = Patient.objects.create(
            first_name="Jane", last_name="Phiri", sex="F",
            dob=date(1992, 5, 12), phone="+260-911-111",
            national_id="234567/89/2",
            nhima_number="NHIMA-00067890",
            province="copperbelt", district="Ndola", city_town="Ndola",
            compound_village="Kansenshi",
            marital_status="single", occupation="Nurse",
            blood_group="A+", allergies="Penicillin",
        )

        # A pediatric patient — demonstrates the required-guardian flow
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

        # Visit 1: John, fully completed
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
            findings="Lung fields clear. No focal consolidation.",
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

        # ── Billing for visit 1: fully self-paid ─────────────────────
        inv1 = Invoice.objects.create(
            visit=v1, patient=john, currency="ZMW",
            status=Invoice.Status.ISSUED,
            issued_at=now - timedelta(hours=2, minutes=50),
            due_at=now + timedelta(days=7),
        )
        InvoiceItem.objects.create(
            invoice=inv1, category=InvoiceItem.Category.CONSULTATION,
            description="OPD consultation", quantity=1, unit_price=150,
        )
        InvoiceItem.objects.create(
            invoice=inv1, category=InvoiceItem.Category.LAB,
            description="CBC", quantity=1, unit_price=80,
            order_item_code="CBC",
        )
        InvoiceItem.objects.create(
            invoice=inv1, category=InvoiceItem.Category.RADIOLOGY,
            description="Chest X-ray PA", quantity=1, unit_price=120,
            order_item_code="CXR-PA",
        )
        InvoiceItem.objects.create(
            invoice=inv1, category=InvoiceItem.Category.PHARMACY,
            description="Paracetamol 500 mg × 9", quantity=1, unit_price=18,
            order_item_code="PARA500",
        )
        inv1.recalculate()
        Payment.objects.create(
            invoice=inv1, amount=inv1.total, method=Payment.Method.CASH,
            reference="CASH-001", received_by=users["admin"],
        )

        # Visit 2: Jane, in consultation
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
            objective="Temp 38.5, pharynx erythematous",
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

        # ── Insurance catalog + Jane's policy ────────────────────────
        nhima, _ = InsuranceProvider.objects.get_or_create(
            tenant=tenant, code="NHIMA",
            defaults=dict(
                name="National Health Insurance (NHIMA)",
                contact_email="claims@nhima.example",
                contact_phone="+260-211-000",
            ),
        )
        madison, _ = InsuranceProvider.objects.get_or_create(
            tenant=tenant, code="MADISON",
            defaults=dict(name="Madison Health", contact_email="claims@madison.example"),
        )

        PatientInsurance.objects.create(
            patient=john, provider=madison,
            policy_number="MH-2025-001", is_primary=True,
        )
        jane_ins = PatientInsurance.objects.create(
            patient=jane, provider=nhima,
            policy_number="NH-2025-998", member_id="JB-5001", is_primary=True,
        )

        # ── Billing for visit 2: insurance + co-pay ─────────────────
        inv2 = Invoice.objects.create(
            visit=v2, patient=jane, currency="ZMW",
            status=Invoice.Status.ISSUED,
            issued_at=now - timedelta(minutes=20),
            due_at=now + timedelta(days=7),
        )
        InvoiceItem.objects.create(
            invoice=inv2, category=InvoiceItem.Category.CONSULTATION,
            description="OPD consultation", quantity=1, unit_price=150,
        )
        InvoiceItem.objects.create(
            invoice=inv2, category=InvoiceItem.Category.LAB,
            description="FBS", quantity=1, unit_price=80,
            order_item_code="FBS",
        )
        InvoiceItem.objects.create(
            invoice=inv2, category=InvoiceItem.Category.RADIOLOGY,
            description="Chest X-ray PA", quantity=1, unit_price=120,
            order_item_code="CXR-PA",
        )
        InvoiceItem.objects.create(
            invoice=inv2, category=InvoiceItem.Category.PHARMACY,
            description="Amoxicillin 500 mg × 21", quantity=1, unit_price=42,
            order_item_code="AMOX500",
        )
        inv2.recalculate()

        # 10% co-pay collected at cashier
        Payment.objects.create(
            invoice=inv2, amount=(inv2.total * Decimal("0.10")).quantize(Decimal("0.01")),
            method=Payment.Method.MOBILE_MONEY, reference="MM-TX-9987",
            received_by=users["admin"],
        )

        # Claim for the remainder
        InsuranceClaim.objects.create(
            invoice=inv2, patient_insurance=jane_ins,
            amount_claimed=(inv2.total * Decimal("0.90")).quantize(Decimal("0.01")),
            status=InsuranceClaim.Status.SUBMITTED,
            submitted_at=now - timedelta(minutes=10),
        )

        # Visit 3: John follow-up, cancelled lab
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
            TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"},
            )
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
                national_id="456789/01/5",
                nhima_number="NHIMA-00099988",
                province="lusaka", district="Lusaka", city_town="Lusaka",
                compound_village="Kabwata",
                marital_status="married", occupation="Accountant",
                blood_group="B+",
            )
            Visit.objects.create(
                patient=mary, visit_type=Visit.Type.OPD,
                status=Visit.Status.OPEN, attending_doctor=doctor_b,
            )

        self.stdout.write(self.style.SUCCESS("   [clinic-b] seeded"))

    def _ensure_superadmin(self):
        """Force-create or update the Platform Admin with NO tenant."""
        from django.contrib.auth.hashers import make_password
        from tenants.models import User
        
        user, created = User.objects.update_or_create(
            email="superadmin@nimbus.local",
            defaults={
                "password": make_password("demo"),
                "first_name": "Super",
                "last_name": "Admin",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_platform_admin": True,
                "tenant": None,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                "   [superadmin] CREATED: superadmin@nimbus.local / demo"))
        else:
            self.stdout.write(self.style.SUCCESS(
                "   [superadmin] UPDATED password to 'demo'"))

