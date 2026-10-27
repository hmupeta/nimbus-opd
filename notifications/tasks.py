import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from common.context import db_tenant_context
from lab.models import LabResult
from billing.models import InsuranceClaim
from appointments.models import Appointment

from .models import SmsLog

logger = logging.getLogger(__name__)


def _send_sms_real(tenant, phone, message):
    """Mock/stub function for a real SMS provider."""
    from tenants.models import SmsConfig

    config = SmsConfig.objects.filter(tenant=tenant, is_active=True).first()
    if not config:
        return False, "No active SMS config found."

    # ── DEV MODE FALLBACK ──────────────────────────────────────────────
    print(f"\n--- MOCK SMS via {config.get_provider_display()} ---")
    print(f"To: {phone}")
    print(f"Message: {message}")
    print("---------------------------------\n")

    # In production, swap this for the real provider call:
    #   Africa's Talking: POST https://api.africastalking.com/version1/messaging
    #   Twilio:           POST https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json
    return True, f"mock-{timezone.now().timestamp()}"


# ──────────────────────────────────────────────────────────────────────
# Email tasks (original behaviour, still required by signals.py)
# ──────────────────────────────────────────────────────────────────────
@shared_task
def notify_doctor_lab_result_ready(lab_result_id: int):
    """Email the attending doctor when a lab result is finalized, and
    send the patient an SMS saying their results are ready."""
    try:
        result = LabResult.all_objects.select_related(
            "lab_order__visit__attending_doctor",
            "lab_order__visit__patient",
            "lab_order__test",
            "tenant",
        ).get(id=lab_result_id)
    except LabResult.DoesNotExist:
        return f"LabResult {lab_result_id} not found"

    doctor = result.lab_order.visit.attending_doctor
    if not doctor or not doctor.email:
        return "No doctor assigned or missing email"

    patient = result.lab_order.visit.patient
    test_name = result.lab_order.test.name

    subject = f"[OPD] Lab Result Ready: {test_name} for {patient.full_name}"
    message = (
        f"Hello Dr. {doctor.last_name},\n\n"
        f"The {test_name} result for {patient.full_name} (MRN: {patient.mrn}) is ready.\n"
        f"Result: {result.value_text} {result.unit} (Flag: {result.get_flag_display()})\n\n"
        f"Please log in to review."
    )

    with db_tenant_context(result.tenant):
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor.email],
            fail_silently=False,
        )

        if patient.phone:
            sms_text = (
                f"Hello {patient.first_name}, your lab results are ready. "
                f"Please check with the clinic."
            )
            log = SmsLog.objects.create(
                tenant=result.tenant, recipient=patient.phone, message=sms_text,
            )
            success, provider_resp = _send_sms_real(
                result.tenant, patient.phone, sms_text)
            if success:
                log.status = SmsLog.Status.SENT
                log.sent_at = timezone.now()
                log.provider_message_id = provider_resp
            else:
                log.status = SmsLog.Status.FAILED
                log.error_message = provider_resp
            log.save()

    return "Notified doctor and patient"


@shared_task
def notify_receptionist_claim_approved(claim_id: int):
    """Email the admin/reception team when an insurance claim is approved."""
    try:
        claim = InsuranceClaim.all_objects.select_related(
            "invoice__patient", "tenant",
        ).get(id=claim_id)
    except InsuranceClaim.DoesNotExist:
        return f"Claim {claim_id} not found"

    patient = claim.invoice.patient
    provider = claim.patient_insurance.provider.name
    amount = claim.amount_approved or 0.00

    subject = f"[OPD] Claim Approved: {provider} for {patient.full_name}"
    message = (
        f"Good news,\n\n"
        f"The claim #{claim.claim_no} submitted to {provider} for "
        f"{patient.full_name} has been APPROVED.\n"
        f"Approved Amount: {amount} {claim.invoice.currency}\n\n"
        f"Please log in to process the final settlement."
    )

    with db_tenant_context(claim.tenant):
        from tenants.models import User
        recipient = User.objects.filter(
            tenant=claim.tenant, role="admin", is_active=True,
        ).first()

        if not recipient or not recipient.email:
            return "No admin recipient found"

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
    return f"Emailed claim approval to {recipient.email}"


# ──────────────────────────────────────────────────────────────────────
# SMS tasks
# ──────────────────────────────────────────────────────────────────────
@shared_task
def notify_patient_appointment(appointment_id: int):
    """SMS the patient with their appointment confirmation details."""
    try:
        appt = Appointment.all_objects.select_related(
            "patient", "doctor", "tenant",
        ).get(id=appointment_id)
    except Appointment.DoesNotExist:
        return "Appointment not found"

    patient = appt.patient
    if not patient.phone:
        return "Patient has no phone number"

    time_str = appt.scheduled_start.strftime("%Y-%m-%d %H:%M")
    sms_text = (
        f"Hello {patient.first_name}, your appointment with "
        f"Dr. {appt.doctor.last_name} is confirmed for {time_str}."
    )

    with db_tenant_context(appt.tenant):
        log = SmsLog.objects.create(
            tenant=appt.tenant, recipient=patient.phone, message=sms_text,
        )
        success, provider_resp = _send_sms_real(
            appt.tenant, patient.phone, sms_text)
        if success:
            log.status = SmsLog.Status.SENT
            log.sent_at = timezone.now()
            log.provider_message_id = provider_resp
        else:
            log.status = SmsLog.Status.FAILED
            log.error_message = provider_resp
        log.save()

    return f"SMS sent to {patient.phone}"
