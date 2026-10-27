from rest_framework import serializers

from clinical.models import ClinicalNote, Order, OrderItem
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import Tenant, TenantSettings, User
from visits.models import Visit
from vitals.models import VitalDefinition, Vitals, VitalValue


class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSettings
        exclude = ["tenant"]


class TenantSerializer(serializers.ModelSerializer):
    settings = TenantSettingsSerializer(read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id", "code", "name", "legal_name", "registration_number",
            "email", "phone", "website",
            "address_line_1", "address_line_2", "city", "state_province",
            "country", "postal_code", "logo",
            "is_active", "created_at", "settings",
        ]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role",
                  "tenant", "is_active", "password"]
        read_only_fields = ["id", "tenant"]

    def create(self, validated):
        pw = validated.pop("password", None)
        user = User(**validated)
        if pw:
            user.set_password(pw)
        user.save()
        return user

    def update(self, instance, validated):
        pw = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if pw:
            instance.set_password(pw)
        instance.save()
        return instance


class PatientSerializer(serializers.ModelSerializer):
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
        return data


class VisitSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = Visit
        fields = ["id", "visit_no", "patient", "patient_name", "visit_type",
                  "status", "arrived_at", "closed_at", "attending_doctor"]
        read_only_fields = ["id", "visit_no", "arrived_at", "closed_at"]

    def validate_patient(self, patient):
        req = self.context.get("request")
        if req and patient.tenant_id != req.user.tenant_id:
            raise serializers.ValidationError("Patient belongs to another tenant")
        return patient


class VitalsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vitals
        fields = ["id", "visit", "recorded_by", "recorded_at",
                  "temperature_c", "weight_kg", "height_cm", "bmi",
                  "systolic", "diastolic", "pulse", "respiratory_rate",
                  "spo2", "pain_score", "notes"]
        read_only_fields = ["id", "recorded_at", "recorded_by"]


class VitalDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VitalDefinition
        fields = ["id", "code", "label", "unit", "data_type", "is_active"]
        read_only_fields = ["id"]


class VitalValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = VitalValue
        fields = ["id", "visit", "definition", "value_num", "value_text",
                  "recorded_by", "recorded_at"]
        read_only_fields = ["id", "recorded_by", "recorded_at"]


class ClinicalNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalNote
        fields = ["id", "visit", "doctor", "kind", "subjective", "objective",
                  "assessment", "plan", "created_at"]
        read_only_fields = ["id", "created_at", "doctor"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "order", "code", "description", "quantity", "instructions"]
        read_only_fields = ["id"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "visit", "ordered_by", "kind", "status", "priority",
                  "notes", "created_at", "items"]
        read_only_fields = ["id", "created_at", "ordered_by"]


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ["id", "code", "name", "specimen_type", "unit",
                  "ref_low", "ref_high", "is_active"]
        read_only_fields = ["id"]


class LabResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabResult
        fields = ["id", "lab_order", "value_text", "unit", "flag",
                  "comment", "resulted_by", "resulted_at", "verified_by"]
        read_only_fields = ["id", "resulted_at", "resulted_by"]



class LabOrderSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    test_code = serializers.CharField(source="test.code", read_only=True)
    result = LabResultSerializer(read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)

    class Meta:
        model = LabOrder
        fields = ["id", "visit", "order", "test", "test_name", "test_code", "status",
                  "patient_name", "result",
                  "ordered_at", "collected_at", "completed_at", "collected_by"]
        read_only_fields = ["id", "ordered_at", "collected_at",
                            "completed_at", "collected_by"]



class RadiologyOrderSerializer(serializers.ModelSerializer):
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)

    class Meta:
        model = RadiologyOrder
        fields = ["id", "visit", "visit_no", "patient_name", "order", "modality", "body_part", "status",
                  "ordered_at", "performed_at", "performed_by",
                  "findings", "impression", "radiologist",
                  "report_url", "image", "reported_at"]
        read_only_fields = ["id", "ordered_at", "performed_at", "reported_at"]


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = ["id", "code", "name", "form", "strength", "unit", "is_active"]
        read_only_fields = ["id"]


class PharmacyItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    class Meta:
        model = PharmacyItem
        fields = ["id", "pharmacy_order", "medicine", "medicine_name", "dose", "frequency",
                  "duration_days", "route", "quantity_prescribed",
                  "quantity_dispensed", "batch_no", "expiry_date"]
        read_only_fields = ["id"]


class PharmacyOrderSerializer(serializers.ModelSerializer):
    items = PharmacyItemSerializer(many=True, read_only=True)
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)

    class Meta:
        model = PharmacyOrder
        fields = ["id", "visit", "visit_no", "patient_name", "order", "status", "dispensed_by",
                  "dispensed_at", "notes", "items"]
        read_only_fields = ["id", "dispensed_by", "dispensed_at"]


class StockSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    class Meta:
        model = Stock
        fields = ["id", "medicine", "medicine_name", "batch_no", "expiry_date", "quantity"]
        read_only_fields = ["id"]


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = ["id", "medicine", "batch_no", "change_qty", "reason",
                  "ref_id", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


class VisitTimelineSerializer(serializers.ModelSerializer):
    patient = PatientSerializer(read_only=True)
    vitals = VitalsSerializer(read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)
    orders = OrderSerializer(many=True, read_only=True)
    lab_orders = LabOrderSerializer(many=True, read_only=True)
    rad_orders = RadiologyOrderSerializer(many=True, read_only=True)
    pharm_orders = PharmacyOrderSerializer(many=True, read_only=True)

    class Meta:
        model = Visit
        fields = ["id", "visit_no", "patient", "visit_type", "status",
                  "arrived_at", "closed_at", "attending_doctor",
                  "vitals", "notes", "orders",
                  "lab_orders", "rad_orders", "pharm_orders"]


from audit.models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="System")
    model_name = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "at", "user_email", "action", "model_name", "object_id", "before", "after"]
