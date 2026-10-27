from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from appointments.models import Appointment
from visits.models import Visit
from .appointment_serializers import AppointmentSerializer
from .permissions import require_roles


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtering for schedules
        date = self.request.query_params.get("date")
        doctor = self.request.query_params.get("doctor")
        if date:
            qs = qs.filter(scheduled_start__date=date)
        if doctor:
            qs = qs.filter(doctor_id=doctor)
            
        return qs

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """Convert an appointment into an actual Visit (OPD encounter)."""
        appt = self.get_object()
        
        if appt.status != Appointment.Status.SCHEDULED:
            return Response(
                {"detail": "Only scheduled appointments can be checked in."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if appt.visit:
            return Response(
                {"detail": "Appointment already has a linked visit."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the OPD Visit
        visit = Visit.objects.create(
            patient=appt.patient,
            attending_doctor=appt.doctor,
            visit_type=Visit.Type.OPD,
            status=Visit.Status.OPEN,
        )
        
        appt.status = Appointment.Status.CHECKED_IN
        appt.visit = visit
        appt.save()
        
        return Response({
            "detail": "Checked in successfully.",
            "visit_id": visit.id,
            "visit_no": visit.visit_no
        })
