#!/usr/bin/env python3
"""
extend_appointments.py -- Add Appointment Scheduling to the OPD system.
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


# ─── 1. Create the appointments app ────────────────────────────────────
if not (ROOT / "appointments").exists():
    sh(PY, "manage.py", "startapp", "appointments")

# ─── 2. Models ─────────────────────────────────────────────────────────
write("appointments/models.py", '''\
from django.db import models
from common.models import TenantAwareModel
from django.core.exceptions import ValidationError


class Appointment(TenantAwareModel):
    class Status(models.TextChoices):
        SCHEDULED   = "scheduled", "Scheduled"
        CHECKED_IN  = "checked_in", "Checked In"
        COMPLETED   = "completed", "Completed"
        CANCELLED   = "cancelled", "Cancelled"
        NO_SHOW     = "no_show", "No Show"

    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey("tenants.User", on_delete=models.CASCADE, related_name="appointments")
    
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    reason = models.CharField(max_length=255, blank=True)
    
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(blank=True)
    
    # Link back to the actual visit once they check in
    visit = models.OneToOneField(
        "visits.Visit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="appointment"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_start"]
        indexes = [
            models.Index(fields=["tenant", "doctor", "scheduled_start"]),
            models.Index(fields=["tenant", "patient", "status"]),
        ]

    def clean(self):
        if self.scheduled_end <= self.scheduled_start:
            raise ValidationError("End time must be after start time.")
        
        # Check for overlapping appointments for the same doctor
        if self.doctor_id and self.scheduled_start and self.scheduled_end:
            overlaps = Appointment.all_objects.filter(
                tenant=self.tenant,
                doctor=self.doctor,
                status__in=[self.Status.SCHEDULED, self.Status.CHECKED_IN],
                scheduled_start__lt=self.scheduled_end,
                scheduled_end__gt=self.scheduled_start,
            ).exclude(pk=self.pk)
            
            if overlaps.exists():
                raise ValidationError("Doctor already has an appointment during this time.")

    def __str__(self):
        return f"{self.patient.full_name} with {self.doctor.last_name} at {self.scheduled_start}"
''')

# ─── 3. Admin ──────────────────────────────────────────────────────────
write("appointments/admin.py", '''\
from django.contrib import admin
from common.admin import TenantModelAdmin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(TenantModelAdmin):
    list_display = ("scheduled_start", "patient", "doctor", "status")
    list_filter = ("status", "doctor")
    search_fields = ("patient__first_name", "patient__last_name", "reason")
    autocomplete_fields = ("patient", "doctor")
    readonly_fields = ("created_at", "visit")
    date_hierarchy = "scheduled_start"
''')

# ─── 4. Add appointment FK to Visit ────────────────────────────────────
vp = ROOT / "visits" / "models.py"
v = vp.read_text(encoding="utf-8")
if "appointment" not in v:
    v = v.replace(
        "    attending_doctor = models.ForeignKey(",
        "    appointment = models.OneToOneField('appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_visit')\n"
        "    attending_doctor = models.ForeignKey("
    )
    vp.write_text(v, encoding="utf-8")
    print("   patched visits/models.py (added appointment link)")

# ─── 5. Serializers & Views ────────────────────────────────────────────
write("api/appointment_serializers.py", '''\
from rest_framework import serializers
from appointments.models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    doctor_name = serializers.CharField(source="doctor.get_full_name", read_only=True)
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id", "patient", "patient_name", "doctor", "doctor_name",
            "scheduled_start", "scheduled_end", "reason", "status",
            "notes", "visit", "visit_no", "created_at"
        ]
        read_only_fields = ["id", "created_at", "visit"]
''')

write("api/appointment_views.py", '''\
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
            appointment=appt
        )
        
        appt.status = Appointment.Status.CHECKED_IN
        appt.visit = visit
        appt.save()
        
        return Response({
            "detail": "Checked in successfully.",
            "visit_id": visit.id,
            "visit_no": visit.visit_no
        })
''')

# ─── 6. Register Routes & App ──────────────────────────────────────────
print("==> Patching urls & settings")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")
if "appointment_views" not in u:
    u = u.replace(
        "from .tokens import TenantTokenObtainPairView",
        "from .tokens import TenantTokenObtainPairView\n"
        "from .appointment_views import AppointmentViewSet"
    )
    u = u.replace(
        'router.register("visits", VisitViewSet, basename="visit")',
        'router.register("visits", VisitViewSet, basename="visit")\n'
        'router.register("appointments", AppointmentViewSet, basename="appointment")'
    )
    up.write_text(u, encoding="utf-8")

sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if '"appointments",' not in s:
    s = s.replace('"visits",', '"visits",\n    "appointments",')
    sp.write_text(s, encoding="utf-8")

# ─── 7. Migrations & RLS ───────────────────────────────────────────────
print("==> makemigrations")
sh(PY, "manage.py", "makemigrations", "appointments", "visits")

write("common/migrations/0006_rls_appointments.py", '''\
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0001_initial"),
        ("visits", "0002_visit_appointment"),  # Auto-generated name
        ("common", "0005_rls_gateways"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "appointments_appointment" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "appointments_appointment" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "appointments_appointment";
                CREATE POLICY tenant_isolation ON "appointments_appointment"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "appointments_appointment";
                ALTER TABLE "appointments_appointment" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
''')

print("==> migrate")
sh(PY, "manage.py", "migrate")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("\n==> Done. You can now schedule appointments and check patients in.")