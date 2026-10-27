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
