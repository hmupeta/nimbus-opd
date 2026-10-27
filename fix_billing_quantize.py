#!/usr/bin/env python3
"""
fix_billing_quantize.py -- coerce int/float to Decimal in billing models,
                           and fix float literals in seed_demo.
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


# ─── 1. Rewrite billing/models.py with defensive coercion ──────────────
write("billing/models.py", '''\
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from common.models import TenantAwareModel
from patients.models import next_sequence


def _dec(value) -> Decimal:
    """Coerce anything (int, float, str, Decimal, None) to Decimal safely."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class InsuranceProvider(TenantAwareModel):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, help_text="Short unique code (e.g. NHIMA)")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"],
                                    name="uniq_insurer_code"),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class PatientInsurance(TenantAwareModel):
    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE,
                                related_name="insurances")
    provider = models.ForeignKey(InsuranceProvider, on_delete=models.PROTECT,
                                 related_name="policies")
    policy_number = models.CharField(max_length=64)
    member_id = models.CharField(max_length=64, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "patient"],
                condition=models.Q(is_primary=True, is_active=True),
                name="uniq_primary_insurance_per_patient",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "patient", "is_active"])]

    def __str__(self):
        return f"{self.patient.full_name} – {self.provider.code} {self.policy_number}"


class Invoice(TenantAwareModel):
    class Status(models.TextChoices):
        DRAFT       = "draft", "Draft"
        ISSUED      = "issued", "Issued"
        PART_PAID   = "part_paid", "Partially paid"
        PAID        = "paid", "Paid"
        CANCELLED   = "cancelled", "Cancelled"
        WRITTEN_OFF = "written_off", "Written off"

    visit = models.ForeignKey("visits.Visit", on_delete=models.PROTECT,
                              related_name="invoices")
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT,
                                related_name="invoices")
    invoice_no = models.CharField(max_length=32, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices,
                              default=Status.DRAFT)
    currency = models.CharField(max_length=3, default="ZMW")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    balance  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    due_at    = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "invoice_no"],
                                    name="uniq_invoice_no"),
        ]
        indexes = [
            models.Index(fields=["tenant", "visit"]),
            models.Index(fields=["tenant", "status"]),
        ]
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            self.invoice_no = f"INV-{next_sequence(self.tenant, 'invoice'):08d}"
        # Coerce money fields up-front so arithmetic never hits int/float
        self.subtotal = _dec(self.subtotal)
        self.discount = _dec(self.discount)
        self.tax      = _dec(self.tax)
        self.total    = _dec(self.total)
        self.balance  = _dec(self.balance)
        super().save(*args, **kwargs)

    def recalculate(self):
        items = self.items.aggregate(s=models.Sum("total"))["s"] or Decimal("0.00")
        self.subtotal = _dec(items).quantize(Decimal("0.01"))
        self.discount = _dec(self.discount).quantize(Decimal("0.01"))
        self.tax      = _dec(self.tax).quantize(Decimal("0.01"))
        self.total = (self.subtotal - self.discount + self.tax).quantize(Decimal("0.01"))

        paid = self.payments.aggregate(s=models.Sum("amount"))["s"] or Decimal("0.00")
        paid = _dec(paid).quantize(Decimal("0.01"))
        self.balance = (self.total - paid).quantize(Decimal("0.01"))

        if self.status not in (self.Status.CANCELLED, self.Status.WRITTEN_OFF):
            if self.balance <= 0 and paid > 0:
                self.status = self.Status.PAID
            elif paid > 0:
                self.status = self.Status.PART_PAID
            elif self.status == self.Status.DRAFT:
                pass
            else:
                self.status = self.Status.ISSUED

        self.save(update_fields=[
            "subtotal", "discount", "tax", "total", "balance", "status",
        ])

    def __str__(self):
        return f"{self.invoice_no} ({self.patient.full_name})"


class InvoiceItem(TenantAwareModel):
    class Category(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        LAB          = "lab", "Laboratory"
        RADIOLOGY    = "radiology", "Radiology"
        PHARMACY     = "pharmacy", "Pharmacy"
        PROCEDURE    = "procedure", "Procedure"
        OTHER        = "other", "Other"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    category = models.CharField(max_length=16, choices=Category.choices)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2,
                                     validators=[MinValueValidator(Decimal("0.00"))])
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False,
                                default=Decimal("0.00"))
    order_item_code = models.CharField(max_length=64, blank=True)

    def save(self, *args, **kwargs):
        self.unit_price = _dec(self.unit_price).quantize(Decimal("0.01"))
        qty = _dec(self.quantity)
        self.total = (self.unit_price * qty).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} × {self.quantity}"


class Payment(TenantAwareModel):
    class Method(models.TextChoices):
        CASH           = "cash", "Cash"
        CARD           = "card", "Card"
        MOBILE_MONEY   = "mobile_money", "Mobile Money"
        BANK_TRANSFER  = "bank_transfer", "Bank Transfer"
        INSURANCE      = "insurance", "Insurance"
        OTHER          = "other", "Other"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT,
                                related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=16, choices=Method.choices,
                              default=Method.CASH)
    reference = models.CharField(max_length=128, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT,
                                    related_name="+")
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "invoice"])]

    def save(self, *args, **kwargs):
        self.amount = _dec(self.amount).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
        self.invoice.recalculate()

    def delete(self, *args, **kwargs):
        inv = self.invoice
        super().delete(*args, **kwargs)
        inv.recalculate()

    def __str__(self):
        return f"{self.amount} {self.invoice.currency} – {self.get_method_display()}"


class InsuranceClaim(TenantAwareModel):
    class Status(models.TextChoices):
        DRAFT        = "draft", "Draft"
        SUBMITTED    = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED     = "approved", "Approved"
        PARTIAL      = "partial", "Partially approved"
        REJECTED     = "rejected", "Rejected"
        PAID         = "paid", "Paid"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT,
                                related_name="claims")
    patient_insurance = models.ForeignKey(PatientInsurance, on_delete=models.PROTECT,
                                          related_name="claims")
    claim_no = models.CharField(max_length=32, blank=True, db_index=True)
    amount_claimed = models.DecimalField(max_digits=12, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=12, decimal_places=2,
                                          null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices,
                              default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at   = models.DateTimeField(null=True, blank=True)
    paid_at      = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "claim_no"],
                                    name="uniq_claim_no"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "invoice"]),
        ]

    def save(self, *args, **kwargs):
        if not self.claim_no:
            self.claim_no = f"CLM-{next_sequence(self.tenant, 'claim'):08d}"
        self.amount_claimed = _dec(self.amount_claimed).quantize(Decimal("0.01"))
        if self.amount_approved is not None:
            self.amount_approved = _dec(self.amount_approved).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.claim_no} – {self.get_status_display()}"
''')

# ─── 2. Patch seed_demo.py ─────────────────────────────────────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

# a) Add Decimal import at top
if "from decimal import Decimal" not in seed:
    seed = seed.replace(
        "from datetime import date, datetime, timedelta, timezone as dt_timezone",
        "from datetime import date, datetime, timedelta, timezone as dt_timezone\n"
        "from decimal import Decimal",
    )

# b) Fix the reset deletion order — move billing BEFORE Visit/Patient
old_order = '''        StockMovement, Stock,
        PharmacyItem, PharmacyOrder,
        LabResult, LabOrder, RadiologyOrder,
        OrderItem, Order,
        ClinicalNote,
        VitalValue, Vitals, VitalDefinition,
        Visit, Patient,
        LabTest, Medicine,
        TenantSequence,
        TenantSettings,
        InsuranceClaim, Payment, InvoiceItem, Invoice, PatientInsurance,
        InsuranceProvider,
        AuditLog,
        User,'''

new_order = '''        # Billing first — Invoice references Visit and Patient with PROTECT
        InsuranceClaim, Payment, InvoiceItem, Invoice,
        PatientInsurance, InsuranceProvider,
        # Clinical
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
        AuditLog,
        User,'''

if old_order in seed:
    seed = seed.replace(old_order, new_order)
    print("   reordered _reset_tenant (billing before clinical)")
else:
    print("   [warn] _reset_tenant order not matched — inspect by hand")

# c) Replace float literals with Decimal literals
seed = seed.replace(
    '(inv2.total * 0.10).quantize(__import__("decimal").Decimal("0.01"))',
    '(inv2.total * Decimal("0.10")).quantize(Decimal("0.01"))',
)
seed = seed.replace(
    '(inv2.total * 0.90).quantize(__import__("decimal").Decimal("0.01"))',
    '(inv2.total * Decimal("0.90")).quantize(Decimal("0.01"))',
)

seed_path.write_text(seed, encoding="utf-8")
print("   patched seed_demo.py (Decimal literals)")

# ─── 3. Make sure no new migrations are required ──────────────────────
print("==> makemigrations --check billing")
sh(PY, "manage.py", "makemigrations", "--check", "billing")

# ─── 4. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")