#!/usr/bin/env python3
"""
extend_api.py -- add DRF + JWT API layer to the OPD project,
                 and fix the CheckConstraint API change in Django 5.1+.

Run from INSIDE the opd/ folder:
    python extend_api.py
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


# ─── 0. Diagnose Django version ─────────────────────────────────────────
print("==> Django version")
sh(PY, "-c", "import django; print(django.get_version())")

# ─── 1. Fix CheckConstraint API (Django 5.1+ uses condition=) ──────────
print("==> Patching CheckConstraint API (check= -> condition=)")

def patch_check_kwarg(path: Path) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    new = content.replace("check=models.Q(", "condition=models.Q(")
    if new != content:
        path.write_text(new, encoding="utf-8")
        print(f"   patched {path.relative_to(ROOT.parent)}")
        return True
    return False


patched = 0
targets = [ROOT / "pharmacy" / "models.py"]
targets += list((ROOT / "pharmacy" / "migrations").glob("*.py"))
# Also future-proof the scaffolder if it lives one level up
scaffold_py = ROOT.parent / "scaffold.py"
if scaffold_py.exists():
    targets.append(scaffold_py)

for f in targets:
    if patch_check_kwarg(f):
        patched += 1
if not patched:
    print("   nothing to patch")

# Quick sanity: does Django now load all models?
print("==> manage.py check (pre-API)")
sh(PY, "manage.py", "check")

# ─── 2. Install DRF + SimpleJWT ────────────────────────────────────────
print("==> Installing DRF + SimpleJWT")
sh(PY, "-m", "pip", "install", "--quiet",
   "djangorestframework>=3.15", "djangorestframework-simplejwt>=5.3")

# ─── 3. Create api app ─────────────────────────────────────────────────
if not (ROOT / "api").exists():
    sh(PY, "manage.py", "startapp", "api")
else:
    print("   api/ already exists - skipping startapp")

# ─── 4. Write api files ────────────────────────────────────────────────
write("api/apps.py", '''\
from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
''')

write("api/auth.py", '''\
from django.db import connection
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from common.context import set_current_tenant


class TenantJWTAuthentication(JWTAuthentication):
    """Authenticate via JWT, then bind the tenant in the DB session.

    Requires ATOMIC_REQUESTS=True so set_config(..., true) persists for the
    whole request.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if getattr(user, "tenant_id", None):
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    [str(user.tenant_id)],
                )
            set_current_tenant(user.tenant)
        return user


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.get_full_name() or user.email
        return token


class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer
''')

write("api/permissions.py", '''\
from rest_framework.permissions import BasePermission


def require_roles(*roles):
    """Return a permission class that allows only these roles (or superuser)."""
    allowed = set(roles)

    class _HasRole(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(
                u and u.is_authenticated
                and (u.is_superuser or u.role in allowed)
            )

    _HasRole.__name__ = f"Role_{'_'.join(sorted(allowed))}"
    return _HasRole


class TenantHeaderMatch(BasePermission):
    """If X-Tenant-ID is present, it must match the authenticated user's tenant."""

    def has_permission(self, request, view):
        header = request.headers.get("X-Tenant-ID")
        if not header:
            return True
        u = request.user
        return bool(u and u.is_authenticated and str(u.tenant_id) == header)
''')

write("api/serializers.py", '''\
from rest_framework import serializers

from clinical.models import ClinicalNote, Order, OrderItem
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import Tenant, User
from visits.models import Visit
from vitals.models import VitalDefinition, Vitals, VitalValue


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "code", "name", "is_active", "created_at"]
        read_only_fields = fields


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

    class Meta:
        model = Patient
        fields = ["id", "mrn", "first_name", "last_name", "full_name",
                  "dob", "sex", "phone", "email", "address",
                  "national_id", "created_at"]
        read_only_fields = ["id", "mrn", "created_at"]


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


class LabOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabOrder
        fields = ["id", "visit", "order", "test", "status",
                  "ordered_at", "collected_at", "completed_at", "collected_by"]
        read_only_fields = ["id", "ordered_at", "collected_at",
                            "completed_at", "collected_by"]


class LabResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabResult
        fields = ["id", "lab_order", "value_text", "unit", "flag",
                  "comment", "resulted_by", "resulted_at", "verified_by"]
        read_only_fields = ["id", "resulted_at", "resulted_by"]


class RadiologyOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = RadiologyOrder
        fields = ["id", "visit", "order", "modality", "body_part", "status",
                  "ordered_at", "performed_at", "performed_by",
                  "findings", "impression", "radiologist",
                  "report_url", "reported_at"]
        read_only_fields = ["id", "ordered_at", "performed_at", "reported_at"]


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = ["id", "code", "name", "form", "strength", "unit", "is_active"]
        read_only_fields = ["id"]


class PharmacyItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyItem
        fields = ["id", "pharmacy_order", "medicine", "dose", "frequency",
                  "duration_days", "route", "quantity_prescribed",
                  "quantity_dispensed", "batch_no", "expiry_date"]
        read_only_fields = ["id"]


class PharmacyOrderSerializer(serializers.ModelSerializer):
    items = PharmacyItemSerializer(many=True, read_only=True)

    class Meta:
        model = PharmacyOrder
        fields = ["id", "visit", "order", "status", "dispensed_by",
                  "dispensed_at", "notes", "items"]
        read_only_fields = ["id", "dispensed_by", "dispensed_at"]


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ["id", "medicine", "batch_no", "expiry_date", "quantity"]
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
''')

write("api/views.py", '''\
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from clinical.models import ClinicalNote, Order, OrderItem
from common.context import get_current_tenant
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import Tenant, User
from visits.models import Visit
from vitals.models import VitalDefinition, Vitals, VitalValue

from .permissions import require_roles
from .serializers import (
    ClinicalNoteSerializer, LabOrderSerializer, LabResultSerializer,
    LabTestSerializer, MedicineSerializer, OrderItemSerializer,
    OrderSerializer, PatientSerializer, PharmacyItemSerializer,
    PharmacyOrderSerializer, RadiologyOrderSerializer, StockMovementSerializer,
    StockSerializer, TenantSerializer, UserSerializer, VisitSerializer,
    VisitTimelineSerializer, VitalsSerializer, VitalDefinitionSerializer,
    VitalValueSerializer,
)


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base: all subclasses are tenant-scoped via TenantManager on the model."""
    permission_classes = [IsAuthenticated]


# ── tenants / users ────────────────────────────────────────────────────
class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TenantSerializer
    queryset = Tenant.objects.all()
    permission_classes = [require_roles("admin")]
    lookup_field = "code"

    def get_queryset(self):
        u = self.request.user
        if u.is_platform_admin or u.is_superuser:
            return Tenant.objects.all()
        return Tenant.objects.filter(id=u.tenant_id)


class UserViewSet(TenantScopedViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = [require_roles("admin")]

    def get_queryset(self):
        t = get_current_tenant() or self.request.user.tenant
        if t is None:
            return User.objects.none()
        return User.objects.filter(tenant=t)

    def perform_create(self, serializer):
        t = get_current_tenant() or self.request.user.tenant
        serializer.save(tenant=t)


# ── patients / visits ──────────────────────────────────────────────────
class PatientViewSet(TenantScopedViewSet):
    serializer_class = PatientSerializer
    queryset = Patient.objects.all()
    permission_classes = [require_roles(
        "admin", "receptionist", "doctor", "nurse")]

    def get_queryset(self):
        qs = Patient.objects.all()
        q = self.request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(mrn__icontains=q)
            )
        return qs

    def perform_destroy(self, instance):
        if self.request.user.role != "admin":
            raise PermissionDenied("Only admins can delete patients")
        super().perform_destroy(instance)


class VisitViewSet(TenantScopedViewSet):
    serializer_class = VisitSerializer
    queryset = Visit.objects.all()
    permission_classes = [require_roles(
        "admin", "receptionist", "doctor", "nurse")]

    def get_queryset(self):
        qs = Visit.objects.all()
        st = self.request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        pid = self.request.query_params.get("patient")
        if pid:
            qs = qs.filter(patient_id=pid)
        return qs

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        visit = self.get_object()
        return Response(VisitTimelineSerializer(visit).data)

    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "nurse")])
    def record_vitals(self, request, pk=None):
        visit = self.get_object()
        v, _ = Vitals.objects.get_or_create(
            visit=visit, defaults={"recorded_by": request.user})
        ser = VitalsSerializer(v, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(recorded_by=request.user)
        visit.status = Visit.Status.TRIAGED
        visit.save(update_fields=["status"])
        return Response(ser.data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        visit = self.get_object()
        pending = visit.orders.filter(status__in=[
            Order.Status.PENDING, Order.Status.IN_PROGRESS])
        if pending.exists():
            return Response(
                {"detail": f"{pending.count()} order(s) still open"},
                status=status.HTTP_409_CONFLICT,
            )
        visit.status = Visit.Status.CLOSED
        visit.closed_at = timezone.now()
        visit.save(update_fields=["status", "closed_at"])
        return Response(VisitSerializer(visit).data)


# ── vitals ─────────────────────────────────────────────────────────────
class VitalsViewSet(TenantScopedViewSet):
    serializer_class = VitalsSerializer
    queryset = Vitals.objects.all()
    permission_classes = [require_roles("admin", "nurse", "doctor")]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class VitalDefinitionViewSet(TenantScopedViewSet):
    serializer_class = VitalDefinitionSerializer
    queryset = VitalDefinition.objects.all()
    permission_classes = [require_roles("admin", "nurse")]


class VitalValueViewSet(TenantScopedViewSet):
    serializer_class = VitalValueSerializer
    queryset = VitalValue.objects.all()
    permission_classes = [require_roles("admin", "nurse")]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


# ── clinical ───────────────────────────────────────────────────────────
class ClinicalNoteViewSet(TenantScopedViewSet):
    serializer_class = ClinicalNoteSerializer
    queryset = ClinicalNote.objects.all()
    permission_classes = [require_roles("admin", "doctor")]

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)


class OrderViewSet(TenantScopedViewSet):
    serializer_class = OrderSerializer
    queryset = Order.objects.all()
    permission_classes = [require_roles("admin", "doctor")]

    def perform_create(self, serializer):
        serializer.save(ordered_by=self.request.user)


class OrderItemViewSet(TenantScopedViewSet):
    serializer_class = OrderItemSerializer
    queryset = OrderItem.objects.all()
    permission_classes = [require_roles("admin", "doctor")]


# ── lab ────────────────────────────────────────────────────────────────
class LabTestViewSet(TenantScopedViewSet):
    serializer_class = LabTestSerializer
    queryset = LabTest.objects.all()
    permission_classes = [require_roles("admin", "lab")]


class LabOrderViewSet(TenantScopedViewSet):
    serializer_class = LabOrderSerializer
    queryset = LabOrder.objects.all()
    permission_classes = [require_roles("admin", "lab", "doctor")]

    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "lab")])
    def collect(self, request, pk=None):
        lo = self.get_object()
        lo.status = LabOrder.Status.COLLECTED
        lo.collected_at = timezone.now()
        lo.collected_by = request.user
        lo.save(update_fields=["status", "collected_at", "collected_by"])
        return Response(LabOrderSerializer(lo).data)

    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "lab")])
    def result(self, request, pk=None):
        lo = self.get_object()
        ser = LabResultSerializer(data={**request.data, "lab_order": lo.pk})
        ser.is_valid(raise_exception=True)
        ser.save(resulted_by=request.user)
        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        return Response(ser.data, status=status.HTTP_201_CREATED)


class LabResultViewSet(TenantScopedViewSet):
    serializer_class = LabResultSerializer
    queryset = LabResult.objects.all()
    permission_classes = [require_roles("admin", "lab", "doctor")]

    def perform_create(self, serializer):
        serializer.save(resulted_by=self.request.user)


# ── radiology ──────────────────────────────────────────────────────────
class RadiologyOrderViewSet(TenantScopedViewSet):
    serializer_class = RadiologyOrderSerializer
    queryset = RadiologyOrder.objects.all()
    permission_classes = [require_roles("admin", "radiology", "doctor")]

    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "radiology")])
    def report(self, request, pk=None):
        ro = self.get_object()
        ser = RadiologyOrderSerializer(ro, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(
            radiologist=request.user,
            status=RadiologyOrder.Status.REPORTED,
            reported_at=timezone.now(),
        )
        return Response(ser.data)


# ── pharmacy ───────────────────────────────────────────────────────────
class MedicineViewSet(TenantScopedViewSet):
    serializer_class = MedicineSerializer
    queryset = Medicine.objects.all()
    permission_classes = [require_roles("admin", "pharmacist")]


class PharmacyOrderViewSet(TenantScopedViewSet):
    serializer_class = PharmacyOrderSerializer
    queryset = PharmacyOrder.objects.all()
    permission_classes = [require_roles("admin", "pharmacist", "doctor")]

    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "pharmacist")])
    def dispense(self, request, pk=None):
        po = self.get_object()
        if po.status == PharmacyOrder.Status.DISPENSED:
            return Response({"detail": "Already dispensed"},
                            status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            for item in po.items.select_related("medicine"):
                qty = item.quantity_prescribed - item.quantity_dispensed
                if qty <= 0:
                    continue
                stocks = (Stock.objects
                          .select_for_update()
                          .filter(medicine=item.medicine, quantity__gt=0)
                          .order_by("expiry_date"))
                for s in stocks:
                    if qty <= 0:
                        break
                    take = min(qty, s.quantity)
                    s.quantity -= take
                    s.save(update_fields=["quantity"])
                    StockMovement.objects.create(
                        medicine=item.medicine, batch_no=s.batch_no,
                        change_qty=-take, reason="dispense",
                        ref_id=po.id, created_by=request.user,
                    )
                    qty -= take
                if qty > 0:
                    return Response(
                        {"detail": f"Insufficient stock for {item.medicine.code}"},
                        status=status.HTTP_409_CONFLICT,
                    )
                item.quantity_dispensed = item.quantity_prescribed
                item.save(update_fields=["quantity_dispensed"])

            po.status = PharmacyOrder.Status.DISPENSED
            po.dispensed_by = request.user
            po.dispensed_at = timezone.now()
            po.save(update_fields=["status", "dispensed_by", "dispensed_at"])
        return Response(PharmacyOrderSerializer(po).data)


class PharmacyItemViewSet(TenantScopedViewSet):
    serializer_class = PharmacyItemSerializer
    queryset = PharmacyItem.objects.all()
    permission_classes = [require_roles("admin", "pharmacist")]


class StockViewSet(TenantScopedViewSet):
    serializer_class = StockSerializer
    queryset = Stock.objects.all()
    permission_classes = [require_roles("admin", "pharmacist")]


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.all()
    permission_classes = [require_roles("admin", "pharmacist")]
''')

write("api/urls.py", '''\
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .auth import TenantTokenObtainPairView
from .views import (
    ClinicalNoteViewSet, LabOrderViewSet, LabResultViewSet, LabTestViewSet,
    MedicineViewSet, OrderItemViewSet, OrderViewSet, PatientViewSet,
    PharmacyItemViewSet, PharmacyOrderViewSet, RadiologyOrderViewSet,
    StockMovementViewSet, StockViewSet, TenantViewSet, UserViewSet,
    VisitViewSet, VitalsViewSet, VitalDefinitionViewSet, VitalValueViewSet,
)

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("users", UserViewSet, basename="user")
router.register("patients", PatientViewSet, basename="patient")
router.register("visits", VisitViewSet, basename="visit")
router.register("vitals", VitalsViewSet, basename="vitals")
router.register("vital-definitions", VitalDefinitionViewSet, basename="vital-def")
router.register("vital-values", VitalValueViewSet, basename="vital-value")
router.register("notes", ClinicalNoteViewSet, basename="note")
router.register("orders", OrderViewSet, basename="order")
router.register("order-items", OrderItemViewSet, basename="order-item")
router.register("lab-tests", LabTestViewSet, basename="lab-test")
router.register("lab-orders", LabOrderViewSet, basename="lab-order")
router.register("lab-results", LabResultViewSet, basename="lab-result")
router.register("radiology-orders", RadiologyOrderViewSet, basename="rad-order")
router.register("medicines", MedicineViewSet, basename="medicine")
router.register("pharmacy-orders", PharmacyOrderViewSet, basename="pharm-order")
router.register("pharmacy-items", PharmacyItemViewSet, basename="pharm-item")
router.register("stock", StockViewSet, basename="stock")
router.register("stock-movements", StockMovementViewSet, basename="stock-mv")

urlpatterns = [
    path("auth/login/", TenantTokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("", include(router.urls)),
]
''')

# ─── 5. Patch settings.py ──────────────────────────────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

if '"rest_framework",' not in s:
    s = s.replace(
        '"django.contrib.staticfiles",',
        '"django.contrib.staticfiles",\n'
        '    "rest_framework",\n'
        '    "rest_framework_simplejwt",\n'
        '    "api",',
    )

if '"ATOMIC_REQUESTS"' not in s:
    s = s.replace(
        '"CONN_MAX_AGE": 60,',
        '"CONN_MAX_AGE": 60,\n        "ATOMIC_REQUESTS": True,',
    )

if "REST_FRAMEWORK = {" not in s:
    s += '''

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.auth.TenantJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "api.permissions.TenantHeaderMatch",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  __import__("datetime").timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": __import__("datetime").timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES":      ("Bearer",),
}
'''
sp.write_text(s, encoding="utf-8")
print("   patched config/settings.py")

# ─── 6. Patch urls.py ──────────────────────────────────────────────────
print("==> Patching config/urls.py")
up = ROOT / "config" / "urls.py"
u = up.read_text(encoding="utf-8")

if "api.urls" not in u:
    if "from django.urls import include, path" not in u:
        u = u.replace(
            "from django.urls import path",
            "from django.urls import include, path",
        )
    u = u.replace(
        'urlpatterns = [path("admin/", admin.site.urls)]',
        'urlpatterns = [\n'
        '    path("admin/", admin.site.urls),\n'
        '    path("api/", include("api.urls")),\n'
        ']',
    )
    up.write_text(u, encoding="utf-8")
    print("   patched config/urls.py")

# ─── 7. Final check ────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")
print()
print("Try it:")
print("  $env:DB_USER='opd_app'; $env:DB_PASSWORD='opd_app'")
print("  python manage.py runserver")
print()
print("  # Login:")
print("  $login = Invoke-RestMethod -Method Post `")
print("    -Uri http://127.0.0.1:8000/api/auth/login/ `")
print("    -ContentType 'application/json' `")
print("    -Body '{\"email\":\"admin@demo.local\",\"password\":\"demo\"}'")
print("  $login.access")
print()
print("  # Patients:")
print("  $H = @{ Authorization = \"Bearer $($login.access)\" }")
print("  Invoke-RestMethod -Headers $H http://127.0.0.1:8000/api/patients/")