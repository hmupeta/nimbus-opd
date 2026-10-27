#!/usr/bin/env python3
"""
extend_billing.py -- add Payment & Insurance Tracking to the OPD backend.
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


# ─── 1. Create the billing app ─────────────────────────────────────────
if not (ROOT / "billing").exists():
    sh(PY, "manage.py", "startapp", "billing")
else:
    print("   billing/ already exists, reusing")

# ─── 2. Models ─────────────────────────────────────────────────────────
write("billing/models.py", '''\
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from common.models import TenantAwareModel
from patients.models import next_sequence


class InsuranceProvider(TenantAwareModel):
    """Tenant-scoped catalog of accepted insurance companies."""

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
    """A patient's policy with a specific provider."""

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
        DRAFT      = "draft", "Draft"
        ISSUED     = "issued", "Issued"
        PART_PAID  = "part_paid", "Partially paid"
        PAID       = "paid", "Paid"
        CANCELLED  = "cancelled", "Cancelled"
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
        super().save(*args, **kwargs)

    def recalculate(self):
        """Sum line items, subtract discount, add tax, compute balance."""
        items = self.items.aggregate(s=models.Sum("total"))["s"] or Decimal("0.00")
        self.subtotal = items
        self.total = (self.subtotal - self.discount + self.tax).quantize(Decimal("0.01"))
        paid = self.payments.aggregate(s=models.Sum("amount"))["s"] or Decimal("0.00")
        self.balance = (self.total - paid).quantize(Decimal("0.01"))

        if self.status not in (self.Status.CANCELLED, self.Status.WRITTEN_OFF):
            if self.balance <= 0 and paid > 0:
                self.status = self.Status.PAID
            elif paid > 0:
                self.status = self.Status.PART_PAID
            elif self.status == self.Status.DRAFT:
                pass  # stay draft
            else:
                self.status = self.Status.ISSUED

        self.save(update_fields=[
            "subtotal", "total", "balance", "status",
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
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    # Optional link back to the clinical order that generated this charge
    order_item_code = models.CharField(max_length=64, blank=True)

    def save(self, *args, **kwargs):
        self.total = (self.unit_price * self.quantity).quantize(Decimal("0.01"))
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
    reference = models.CharField(max_length=128, blank=True,
                                 help_text="Transaction ref / cheque no.")
    paid_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT,
                                    related_name="+")
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "invoice"])]

    def save(self, *args, **kwargs):
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
        DRAFT       = "draft", "Draft"
        SUBMITTED   = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED    = "approved", "Approved"
        PARTIAL     = "partial", "Partially approved"
        REJECTED    = "rejected", "Rejected"
        PAID        = "paid", "Paid"

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
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.claim_no} – {self.get_status_display()}"
''')

# ─── 3. Admin ──────────────────────────────────────────────────────────
write("billing/admin.py", '''\
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
    fields = ("amount", "method", "reference", "paid_at", "received_by")
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
                    "paid_at", "received_by")
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
''')

# ─── 4. Serializers ────────────────────────────────────────────────────
write("api/billing_serializers.py", '''\
from rest_framework import serializers

from billing.models import (
    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,
    PatientInsurance, Payment,
)


class InsuranceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceProvider
        fields = ["id", "name", "code", "contact_email", "contact_phone",
                  "address", "is_active"]
        read_only_fields = ["id"]


class PatientInsuranceSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = PatientInsurance
        fields = ["id", "patient", "patient_name", "provider", "provider_name",
                  "policy_number", "member_id",
                  "valid_from", "valid_to", "is_primary", "is_active"]
        read_only_fields = ["id"]


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["id", "invoice", "category", "description",
                  "quantity", "unit_price", "total", "order_item_code"]
        read_only_fields = ["id", "total"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "invoice", "amount", "method", "reference",
                  "paid_at", "received_by", "notes"]
        read_only_fields = ["id", "received_by"]


class InsuranceClaimSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(
        source="patient_insurance.provider.name", read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = ["id", "invoice", "patient_insurance", "provider_name",
                  "claim_no", "amount_claimed", "amount_approved",
                  "status", "submitted_at", "decided_at", "paid_at",
                  "rejection_reason", "notes", "created_at"]
        read_only_fields = ["id", "claim_no", "created_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    claims = InsuranceClaimSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source="patient.full_name",
                                          read_only=True)
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "invoice_no", "visit", "visit_no",
                  "patient", "patient_name", "status", "currency",
                  "subtotal", "discount", "tax", "total", "balance",
                  "notes", "issued_at", "due_at", "created_at",
                  "items", "payments", "claims"]
        read_only_fields = ["id", "invoice_no", "subtotal", "total",
                            "balance", "created_at"]
''')

# ─── 5. Views ──────────────────────────────────────────────────────────
write("api/billing_views.py", '''\
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.models import (
    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,
    PatientInsurance, Payment,
)

from .billing_serializers import (
    InsuranceClaimSerializer, InsuranceProviderSerializer,
    InvoiceItemSerializer, InvoiceSerializer, PatientInsuranceSerializer,
    PaymentSerializer,
)
from .permissions import require_roles


class InsuranceProviderViewSet(viewsets.ModelViewSet):
    queryset = InsuranceProvider.objects.all()
    serializer_class = InsuranceProviderSerializer
    permission_classes = [require_roles("admin")]


class PatientInsuranceViewSet(viewsets.ModelViewSet):
    queryset = PatientInsurance.objects.all()
    serializer_class = PatientInsuranceSerializer
    permission_classes = [require_roles("admin", "receptionist")]

    def get_queryset(self):
        qs = super().get_queryset()
        pid = self.request.query_params.get("patient")
        if pid:
            qs = qs.filter(patient_id=pid)
        return qs


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        inv = self.get_object()
        if inv.status != Invoice.Status.DRAFT:
            return Response({"detail": "Only drafts can be issued"},
                            status=status.HTTP_409_CONFLICT)
        inv.issued_at = timezone.now()
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["issued_at", "status"])
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        inv = self.get_object()
        inv.recalculate()
        return Response(InvoiceSerializer(inv).data)


class InvoiceItemViewSet(viewsets.ModelViewSet):
    queryset = InvoiceItem.objects.all()
    serializer_class = InvoiceItemSerializer
    permission_classes = [require_roles("admin", "receptionist")]

    def perform_create(self, serializer):
        item = serializer.save()
        item.invoice.recalculate()

    def perform_update(self, serializer):
        item = serializer.save()
        item.invoice.recalculate()

    def perform_destroy(self, instance):
        inv = instance.invoice
        instance.delete()
        inv.recalculate()


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [require_roles("admin", "receptionist", "pharmacist")]

    def get_queryset(self):
        qs = super().get_queryset()
        inv = self.request.query_params.get("invoice")
        if inv:
            qs = qs.filter(invoice_id=inv)
        return qs

    def perform_create(self, serializer):
        serializer.save(received_by=self.request.user)


class InsuranceClaimViewSet(viewsets.ModelViewSet):
    queryset = InsuranceClaim.objects.all()
    serializer_class = InsuranceClaimSerializer
    permission_classes = [require_roles("admin", "receptionist")]

    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("status", "invoice"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        claim = self.get_object()
        if claim.status != InsuranceClaim.Status.DRAFT:
            raise ValidationError("Only drafts can be submitted")
        claim.status = InsuranceClaim.Status.SUBMITTED
        claim.submitted_at = timezone.now()
        claim.save(update_fields=["status", "submitted_at"])
        return Response(InsuranceClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        claim = self.get_object()
        new_status = request.data.get("status")
        if new_status not in (
            InsuranceClaim.Status.APPROVED,
            InsuranceClaim.Status.PARTIAL,
            InsuranceClaim.Status.REJECTED,
        ):
            raise ValidationError("status must be approved, partial or rejected")
        claim.status = new_status
        claim.amount_approved = request.data.get("amount_approved")
        claim.rejection_reason = request.data.get("rejection_reason", "")
        claim.decided_at = timezone.now()
        claim.save()
        return Response(InsuranceClaimSerializer(claim).data)

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        claim = self.get_object()
        if claim.status not in (
            InsuranceClaim.Status.APPROVED,
            InsuranceClaim.Status.PARTIAL,
        ):
            raise ValidationError("Only approved or partial claims can be paid")
        # Create a Payment record for the approved amount
        Payment.objects.create(
            invoice=claim.invoice,
            amount=claim.amount_approved or claim.amount_claimed,
            method=Payment.Method.INSURANCE,
            reference=claim.claim_no,
            received_by=request.user,
            notes=f"Insurance settlement for {claim.claim_no}",
        )
        claim.status = InsuranceClaim.Status.PAID
        claim.paid_at = timezone.now()
        claim.save(update_fields=["status", "paid_at"])
        return Response(InsuranceClaimSerializer(claim).data)
''')

# ─── 6. Register routes in api/urls.py ────────────────────────────────
print("==> Patching api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")

if "billing_views" not in u:
    u = u.replace(
        "from .tokens import TenantTokenObtainPairView",
        "from .tokens import TenantTokenObtainPairView\n"
        "from .billing_views import (\n"
        "    InsuranceClaimViewSet, InsuranceProviderViewSet,\n"
        "    InvoiceItemViewSet, InvoiceViewSet, PatientInsuranceViewSet,\n"
        "    PaymentViewSet,\n"
        ")"
    )
    u = u.replace(
        'router.register("stock-movements", StockMovementViewSet, basename="stock-mv")',
        'router.register("stock-movements", StockMovementViewSet, basename="stock-mv")\n'
        'router.register("insurance-providers", InsuranceProviderViewSet, basename="insurer")\n'
        'router.register("patient-insurances", PatientInsuranceViewSet, basename="patient-ins")\n'
        'router.register("invoices", InvoiceViewSet, basename="invoice")\n'
        'router.register("invoice-items", InvoiceItemViewSet, basename="invoice-item")\n'
        'router.register("payments", PaymentViewSet, basename="payment")\n'
        'router.register("insurance-claims", InsuranceClaimViewSet, basename="claim")'
    )
    up.write_text(u, encoding="utf-8")
    print("   patched api/urls.py")

# ─── 7. Register app in settings ──────────────────────────────────────
print("==> Patching config/settings.py (INSTALLED_APPS)")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if '"billing",' not in s:
    s = s.replace('"audit.apps.AuditConfig",', '"audit.apps.AuditConfig",\n    "billing",')
    sp.write_text(s, encoding="utf-8")
    print("   patched config/settings.py")

# ─── 8. makemigrations billing ────────────────────────────────────────
print("==> makemigrations billing")
sh(PY, "manage.py", "makemigrations", "billing")

# ─── 9. RLS migration for billing tables ──────────────────────────────
write("common/migrations/0003_rls_billing.py", '''\
from django.db import migrations


TENANT_TABLES = [
    "billing_insuranceprovider",
    "billing_patientinsurance",
    "billing_invoice",
    "billing_invoiceitem",
    "billing_payment",
    "billing_insuranceclaim",
]

POLICY_SQL = """
    ALTER TABLE "{tbl}" ENABLE ROW LEVEL SECURITY;
    ALTER TABLE "{tbl}" FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";
    CREATE POLICY tenant_isolation ON "{tbl}"
        USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""


def enable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(POLICY_SQL.format(tbl=tbl))


def disable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{tbl}" DISABLE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";')


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
        ("common", "0002_rls_tenant_settings"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
''')

# ─── 10. migrate ──────────────────────────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 11. Extend seed_demo with billing data ───────────────────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

if "InsuranceProvider" not in seed:
    # imports
    seed = seed.replace(
        "from audit.models import AuditLog",
        "from audit.models import AuditLog\n"
        "from billing.models import (\n"
        "    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,\n"
        "    PatientInsurance, Payment,\n"
        ")"
    )

    # extend reset deletion order — add billing tables before User/AuditLog
    seed = seed.replace(
        "        TenantSequence,\n        TenantSettings,\n        AuditLog,       # existing audit rows (if any)\n        User,",
        "        TenantSequence,\n        TenantSettings,\n"
        "        InsuranceClaim, Payment, InvoiceItem, Invoice, PatientInsurance,\n"
        "        InsuranceProvider,\n"
        "        AuditLog,       # existing audit rows (if any)\n        User,"
    )

    # after the visit-1 pharmacy, add billing block
    seed = seed.replace(
        '''        StockMovement.objects.create(
            medicine=catalog["meds"]["PARA500"], batch_no="PARA-A1",
            change_qty=-9, reason="dispense",
            ref_id=po.id, created_by=users["pharmacy"],
        )''',
        '''        StockMovement.objects.create(
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
        )''',
    )

    # after visit-2 pending pharmacy, add insurance-block + invoices
    seed = seed.replace(
        '''        PharmacyItem.objects.create(
            pharmacy_order=po2, medicine=catalog["meds"]["AMOX500"],
            dose="1 cap", frequency="TID", duration_days=7,
            route="PO", quantity_prescribed=21, quantity_dispensed=0,
        )''',
        '''        PharmacyItem.objects.create(
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
            invoice=inv2, amount=(inv2.total * 0.10).quantize(__import__("decimal").Decimal("0.01")),
            method=Payment.Method.MOBILE_MONEY, reference="MM-TX-9987",
            received_by=users["admin"],
        )

        # Claim for the remainder
        InsuranceClaim.objects.create(
            invoice=inv2, patient_insurance=jane_ins,
            amount_claimed=(inv2.total * 0.90).quantize(__import__("decimal").Decimal("0.01")),
            status=InsuranceClaim.Status.SUBMITTED,
            submitted_at=now - timedelta(minutes=10),
        )''',
    )

    seed_path.write_text(seed, encoding="utf-8")
    print("   patched seed_demo.py")

# ─── 12. Reseed with billing data ─────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Restart the server and visit:")
print("    /api/docs/            → new billing endpoints")
print("    /admin/billing/       → invoice, payment, claim admin")