from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from clinical.models import ClinicalNote, Order, OrderItem
from billing.models import (
    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,
    PatientInsurance, Payment,
)
from common.context import get_current_tenant
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import Tenant, TenantSettings, User
from visits.models import Visit
from vitals.models import VitalDefinition, Vitals, VitalValue

from .permissions import require_roles
from .serializers import TenantSettingsSerializer
from .billing_serializers import InvoiceSerializer
from .serializers import (
    ClinicalNoteSerializer, LabOrderSerializer, LabResultSerializer,
    LabTestSerializer, MedicineSerializer, OrderItemSerializer,
    OrderSerializer, PatientSerializer, PharmacyItemSerializer,
    PharmacyOrderSerializer, RadiologyExamSerializer, RadiologyOrderSerializer, StockMovementSerializer,
    StockSerializer, TenantSerializer, UserSerializer, VisitSerializer,
    VisitTimelineSerializer, VitalsSerializer, VitalDefinitionSerializer,
    VitalValueSerializer,
)


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base: all subclasses are tenant-scoped via TenantManager on the model."""
    permission_classes = [IsAuthenticated]


# ── tenants / users ────────────────────────────────────────────────────

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

class TenantRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from tenants.models import Tenant, TenantSettings, User
        from common.context import db_tenant_context
        from django.db import transaction
        from django.contrib.auth.hashers import make_password
        
        data = request.data
        clinic_name = data.get("clinic_name")
        clinic_code = data.get("clinic_code", "").lower().replace(" ", "-")
        email = data.get("email")
        password = data.get("password")
        first_name = data.get("first_name", "Clinic")
        last_name = data.get("last_name", "Admin")

        if not clinic_name or not clinic_code or not email or not password:
            return Response({"detail": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        if Tenant.objects.filter(code=clinic_code).exists():
            return Response({"detail": "Clinic code already taken. Try another."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"detail": "Email already registered."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # 1. Create Tenant
                tenant = Tenant.objects.create(code=clinic_code, name=clinic_name, is_active=False)
                
                # 2. Create Admin User
                user = User.objects.create(
                    email=email, password=make_password(password),
                    first_name=first_name, last_name=last_name,
                    tenant=tenant, role="admin", is_staff=True, is_superuser=True
                )

                # 3. Create Settings inside tenant context
                with db_tenant_context(tenant):
                    TenantSettings.objects.create(tenant=tenant, timezone="UTC", currency_code="USD")

            return Response({"detail": "Clinic registered successfully! You can now log in."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TenantSerializer
    queryset = Tenant.objects.all()
    permission_classes = [require_roles("admin")]
    lookup_field = "code"

    def get_queryset(self):
        u = self.request.user
        if u.is_platform_admin or u.is_superuser:
            return Tenant.objects.all().order_by('-id')
        return Tenant.objects.filter(id=u.tenant_id)

    @action(detail=True, methods=["patch"], permission_classes=[require_roles("admin")])
    def settings(self, request, code=None):
        tenant = self.get_object()
        # Enforce users can only edit their own tenant's settings unless platform admin
        if not (request.user.is_platform_admin or request.user.is_superuser):
            if request.user.tenant_id != tenant.id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Cannot edit another tenant's settings")
        
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        ser = TenantSettingsSerializer(settings_obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class UserViewSet(TenantScopedViewSet):
    serializer_class = UserSerializer
    def get_queryset(self):
        return User.objects.all().order_by('-id')
    permission_classes = [require_roles("admin")]

    def get_queryset(self):
        t = get_current_tenant() or self.request.user.tenant
        if t is None:
            return User.objects.none()
        qs = User.objects.filter(tenant=t).order_by("-id")
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        return qs

    def perform_create(self, serializer):
        t = get_current_tenant() or self.request.user.tenant
        serializer.save(tenant=t)


# ── patients / visits ──────────────────────────────────────────────────
class PatientViewSet(TenantScopedViewSet):
    serializer_class = PatientSerializer
    queryset = Patient.objects.all()
    permission_classes = [require_roles("admin", "receptionist", "doctor", "nurse", "pharmacist", "lab")]

    def get_queryset(self):
        qs = Patient.objects.all().order_by("-id")
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

    def create(self, request, *args, **kwargs):
        if request.user.role not in ["admin", "receptionist"]:
            return Response(
                {"detail": "Only a Receptionist or Admin can start a new visit."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)


    def get_queryset(self):
        qs = Visit.objects.all().order_by("-id")
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

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
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

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_lab(self, request, pk=None):
        visit = self.get_object()
        test_id = request.data.get("test")
        custom_test_name = request.data.get("custom_test_name")

        if not test_id and not custom_test_name:
            return Response({"detail": "test or custom_test_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        from lab.models import LabTest, LabOrder
        from decimal import Decimal

        if test_id:
            test = LabTest.objects.filter(id=test_id).first()
            if not test:
                return Response({"detail": "Invalid test"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Create a custom test on the fly so it exists in the DB for the lab tech
            test, _ = LabTest.objects.get_or_create(
                tenant=visit.tenant,
                name=custom_test_name,
                defaults={"code": custom_test_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.LAB, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=test.code, description=test.name, quantity=1)
            LabOrder.objects.create(visit=visit, order=order, test=test, status=LabOrder.Status.PENDING)

        return Response({"detail": "Lab ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def prescribe(self, request, pk=None):
        visit = self.get_object()
        med_id = request.data.get("medicine")
        custom_med_name = request.data.get("custom_medicine_name")
        
        dose = request.data.get("dose", "1 tab")
        freq = request.data.get("frequency", "OD")
        duration = request.data.get("duration_days", 1)
        qty = request.data.get("quantity", 1)

        if not med_id and not custom_med_name:
            return Response({"detail": "medicine or custom_medicine_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        from pharmacy.models import Medicine, PharmacyOrder, PharmacyItem
        from decimal import Decimal
        
        if med_id:
            med = Medicine.objects.filter(id=med_id).first()
            if not med:
                return Response({"detail": "Invalid medicine"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            med, _ = Medicine.objects.get_or_create(
                tenant=visit.tenant, name=custom_med_name,
                defaults={"code": custom_med_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.PHARMACY, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=med.code, description=med.name, quantity=qty)
            p_order = PharmacyOrder.objects.create(visit=visit, order=order, status=PharmacyOrder.Status.PENDING)
            PharmacyItem.objects.create(
                pharmacy_order=p_order, medicine=med, dose=dose, frequency=freq,
                duration_days=duration, quantity_prescribed=qty
            )

        return Response({"detail": "Prescription added", "order_id": order.id}, status=status.HTTP_201_CREATED)



    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "receptionist")])
    def generate_invoice(self, request, pk=None):
        visit = self.get_object()
        from decimal import Decimal
        if Invoice.all_objects.filter(visit=visit).exists():
            inv = Invoice.all_objects.get(visit=visit)
            return Response(InvoiceSerializer(inv).data)
        
        with transaction.atomic():
            inv = Invoice.objects.create(
                visit=visit, patient=visit.patient, status=Invoice.Status.ISSUED, currency="ZMW"
            )
            # Consultation fee
            InvoiceItem.objects.create(
                invoice=inv, category=InvoiceItem.Category.CONSULTATION,
                description="OPD Consultation", quantity=1, unit_price=Decimal("150.00")
            )
            # Orders
            for order in visit.orders.all():
                for item in order.items.all():
                    price = Decimal("0.00")
                    if order.kind == "lab":
                        from lab.models import LabTest
                        t = LabTest.objects.filter(code=item.code).first()
                        price = t.base_price if t else Decimal("0.00")
                    elif order.kind == "pharmacy":
                        from pharmacy.models import Medicine
                        m = Medicine.objects.filter(code=item.code).first()
                        price = m.base_price if m else Decimal("0.00")
                    elif order.kind == "radiology":
                        price = Decimal("120.00")
                    
                    if price > 0:
                        InvoiceItem.objects.create(
                            invoice=inv, category=order.kind,
                            description=item.description, quantity=item.quantity,
                            unit_price=price, order_item_code=item.code
                        )
            inv.recalculate()
            
        return Response({"detail": "Invoice generated", "invoice_id": inv.id})



    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_radiology(self, request, pk=None):
        visit = self.get_object()
        exam_id = request.data.get("exam")
        custom_modality = request.data.get("custom_modality")
        custom_body_part = request.data.get("custom_body_part")
        notes = request.data.get("notes", "")

        from radiology.models import RadiologyExam, RadiologyOrder
        from decimal import Decimal

        if exam_id:
            exam = RadiologyExam.objects.filter(id=exam_id).first()
            if not exam:
                return Response({"detail": "Invalid exam"}, status=status.HTTP_400_BAD_REQUEST)
            modality = exam.modality
            body_part = exam.body_part
            code = exam.code
            desc = exam.name
            price = exam.base_price
        elif custom_modality and custom_body_part:
            custom_price = request.data.get("custom_price", "0.00")
            modality = custom_modality
            body_part = custom_body_part
            code = f"{modality}-{body_part}"[:32].upper().replace(" ", "-")
            desc = f"{modality} {body_part}"
            price = Decimal(str(custom_price))
            # Save to catalog for next time
            RadiologyExam.objects.get_or_create(
                tenant=visit.tenant, code=code,
                defaults={"name": desc, "modality": modality, "body_part": body_part, "base_price": price}
            )
        else:
            return Response({"detail": "exam or custom details are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.RADIOLOGY, status=Order.Status.PENDING, notes=notes)
            OrderItem.objects.create(order=order, code=code, description=desc, quantity=1)
            RadiologyOrder.objects.create(
                visit=visit, order=order, modality=modality, body_part=body_part, status=RadiologyOrder.Status.PENDING
            )
            
            # Update the price of the auto-generated invoice item later
            # (Handled in the invoice generation logic based on the OrderItem code)

        return Response({"detail": "Radiology ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)

class VitalsViewSet(TenantScopedViewSet):
    serializer_class = VitalsSerializer
    def get_queryset(self):
        return Vitals.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "nurse", "doctor")]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class VitalDefinitionViewSet(TenantScopedViewSet):
    serializer_class = VitalDefinitionSerializer
    def get_queryset(self):
        return VitalDefinition.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "nurse")]


class VitalValueViewSet(TenantScopedViewSet):
    serializer_class = VitalValueSerializer
    def get_queryset(self):
        return VitalValue.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "nurse")]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


# ── clinical ───────────────────────────────────────────────────────────
class ClinicalNoteViewSet(TenantScopedViewSet):
    serializer_class = ClinicalNoteSerializer
    def get_queryset(self):
        return ClinicalNote.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "doctor")]

    def perform_create(self, serializer):
        serializer.save(doctor=self.request.user)


class OrderViewSet(TenantScopedViewSet):
    serializer_class = OrderSerializer
    def get_queryset(self):
        return Order.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "doctor")]

    def perform_create(self, serializer):
        serializer.save(ordered_by=self.request.user)


class OrderItemViewSet(TenantScopedViewSet):
    serializer_class = OrderItemSerializer
    def get_queryset(self):
        return OrderItem.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "doctor")]


# ── lab ────────────────────────────────────────────────────────────────
class LabTestViewSet(TenantScopedViewSet):
    serializer_class = LabTestSerializer
    def get_queryset(self):
        return LabTest.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "lab")]


class LabOrderViewSet(TenantScopedViewSet):
    serializer_class = LabOrderSerializer
    def get_queryset(self):
        return LabOrder.objects.all().order_by('-id')
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
        
        # Use update_or_create to handle both new results and overrides safely
        result, created = LabResult.objects.update_or_create(
            lab_order=lo,
            defaults={
                "tenant": lo.tenant,
                "value_text": request.data.get("value_text"),
                "unit": request.data.get("unit", ""),
                "flag": request.data.get("flag", "normal"),
                "comment": request.data.get("comment", ""),
                "resulted_by": request.user,
            }
        )
        if "attachment" in request.FILES:
            result.attachment = request.FILES["attachment"]
            result.save()


        # Update the parent LabOrder status
        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)


class LabResultViewSet(TenantScopedViewSet):
    serializer_class = LabResultSerializer
    def get_queryset(self):
        return LabResult.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "lab", "doctor")]

    def perform_create(self, serializer):
        serializer.save(resulted_by=self.request.user)


# ── radiology ──────────────────────────────────────────────────────────
class RadiologyExamViewSet(TenantScopedViewSet):
    serializer_class = RadiologyExamSerializer
    permission_classes = [require_roles("admin", "radiology", "doctor", "nurse")]

    def get_queryset(self):
        # Lazy import — works even if the module-level import is missing
        from radiology.models import RadiologyExam
        return RadiologyExam.all_objects.filter(
            tenant_id=self.request.user.tenant_id
        ).order_by("-id")



class RadiologyOrderViewSet(TenantScopedViewSet):
    serializer_class = RadiologyOrderSerializer
    def get_queryset(self):
        return RadiologyOrder.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "radiology", "doctor")]

    @action(detail=True, methods=["post"],
            permission_classes=[require_roles("admin", "radiology")])
    def report(self, request, pk=None):
        ro = self.get_object()
        # request.data handles both JSON and multipart/form-data (files)
        ser = RadiologyOrderSerializer(ro, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ro = ser.save(
            radiologist=request.user,
            status=RadiologyOrder.Status.REPORTED,
            reported_at=timezone.now(),
        )
        
        # Mark the parent order as completed
        ro.order.status = Order.Status.COMPLETED
        ro.order.save(update_fields=["status"])
        
        return Response(ser.data)


# ── pharmacy ───────────────────────────────────────────────────────────
class MedicineViewSet(TenantScopedViewSet):
    serializer_class = MedicineSerializer
    def get_queryset(self):
        return Medicine.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "pharmacist")]


class PharmacyOrderViewSet(TenantScopedViewSet):
    serializer_class = PharmacyOrderSerializer
    def get_queryset(self):
        return PharmacyOrder.objects.all().order_by('-id')
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
            
            # Mark the parent order as completed
            po.order.status = Order.Status.COMPLETED
            po.order.save(update_fields=["status"])
            
        return Response(PharmacyOrderSerializer(po).data)


class PharmacyItemViewSet(TenantScopedViewSet):
    serializer_class = PharmacyItemSerializer
    def get_queryset(self):
        return PharmacyItem.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "pharmacist")]


class StockViewSet(TenantScopedViewSet):
    serializer_class = StockSerializer
    def get_queryset(self):
        return Stock.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "pharmacist")]


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockMovementSerializer
    def get_queryset(self):
        return StockMovement.objects.all().order_by('-id')
    permission_classes = [require_roles("admin", "pharmacist")]
