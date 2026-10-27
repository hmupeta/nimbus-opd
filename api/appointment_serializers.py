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
