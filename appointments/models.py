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
