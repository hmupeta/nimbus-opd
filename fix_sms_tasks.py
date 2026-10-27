#!/usr/bin/env python3
"""
fix_sms_tasks.py -- restore the missing notify_receptionist_claim_approved task,
                    then re-run migrations and seed.
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


def sh(*cmd, env=None):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=env or ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Rewrite notifications/tasks.py with the missing task restored ──
write("notifications/tasks.py", '''\
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
    print(f"\\n--- MOCK SMS via {config.get_provider_display()} ---")
    print(f"To: {phone}")
    print(f"Message: {message}")
    print("---------------------------------\\n")

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
        f"Hello Dr. {doctor.last_name},\\n\\n"
        f"The {test_name} result for {patient.full_name} (MRN: {patient.mrn}) is ready.\\n"
        f"Result: {result.value_text} {result.unit} (Flag: {result.get_flag_display()})\\n\\n"
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
        f"Good news,\\n\\n"
        f"The claim #{claim.claim_no} submitted to {provider} for "
        f"{patient.full_name} has been APPROVED.\\n"
        f"Approved Amount: {amount} {claim.invoice.currency}\\n\\n"
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
''')

# ─── 2. makemigrations ─────────────────────────────────────────────────
print("==> makemigrations tenants notifications")
sh(PY, "manage.py", "makemigrations", "tenants", "notifications")

# ─── 3. RLS migration (written after seeing the real migration names) ──
tenants_migrations = sorted(
    (ROOT / "tenants" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest_tenants = tenants_migrations[-1].stem
notifications_migrations = sorted(
    (ROOT / "notifications" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest_notifications = notifications_migrations[-1].stem

print(f"   newest tenants migration: {latest_tenants}")
print(f"   newest notifications migration: {latest_notifications}")

write("common/migrations/0007_rls_sms.py", f'''\
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "{latest_tenants}"),
        ("notifications", "{latest_notifications}"),
        ("common", "0006_rls_appointments"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_smsconfig" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_smsconfig" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_smsconfig";
                CREATE POLICY tenant_isolation ON "tenants_smsconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

                ALTER TABLE "notifications_smslog" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "notifications_smslog" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "notifications_smslog";
                CREATE POLICY tenant_isolation ON "notifications_smslog"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "notifications_smslog";
                ALTER TABLE "notifications_smslog" DISABLE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_smsconfig";
                ALTER TABLE "tenants_smsconfig" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
''')

# ─── 4. migrate ────────────────────────────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 5. seed_demo (NO_REDIS=1) ─────────────────────────────────────────
print("==> seed_demo --reset (NO_REDIS=1)")
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
subprocess.run([str(PY), "manage.py", "seed_demo", "--reset"],
               check=True, env=seed_env)

# ─── 6. Sanity ─────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. SMS module is fully wired.")