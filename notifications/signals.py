import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from lab.models import LabResult
from billing.models import InsuranceClaim
from appointments.models import Appointment

from .tasks import (
    notify_doctor_lab_result_ready, 
    notify_receptionist_claim_approved, 
    notify_patient_appointment
)

logger = logging.getLogger(__name__)

@receiver(post_save, sender=LabResult)
def trigger_lab_notification(sender, instance, created, **kwargs):
    if created:
        try:
            notify_doctor_lab_result_ready.delay(instance.id)
        except Exception as e:
            logger.error(f"Failed to queue lab notification: {e}")

@receiver(post_save, sender=InsuranceClaim)
def trigger_claim_notification(sender, instance, created, **kwargs):
    if not created and instance.status == InsuranceClaim.Status.APPROVED:
        try:
            notify_receptionist_claim_approved.delay(instance.id)
        except Exception as e:
            logger.error(f"Failed to queue claim notification: {e}")

@receiver(post_save, sender=Appointment)
def trigger_appointment_notification(sender, instance, created, **kwargs):
    if created:
        try:
            notify_patient_appointment.delay(instance.id)
        except Exception as e:
            logger.error(f"Failed to queue appointment SMS: {e}")
