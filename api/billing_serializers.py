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
                  "mobile_money_config", "payment_gateway_config",
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
