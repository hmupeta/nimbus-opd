#!/usr/bin/env python3
"""
add_celery.py -- install Celery, configure Redis, and add notification tasks.
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


# ─── 1. Install Celery & Redis ─────────────────────────────────────────
print("==> Installing Celery and Redis client")
sh(PY, "-m", "pip", "install", "--quiet", "celery>=5.3", "redis>=5.0")

# ─── 2. Create config/celery.py ────────────────────────────────────────
write("config/celery.py", '''\
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("opd")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
''')

# ─── 3. Update config/__init__.py ──────────────────────────────────────
write("config/__init__.py", '''\
from .celery import app as celery_app

__all__ = ("celery_app",)
''')

# ─── 4. Update settings.py ─────────────────────────────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

if "CELERY_BROKER_URL" not in s:
    s += '''

# ─── Celery ────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ─── Email (Console for Dev) ───────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@opd-system.local"
'''
    sp.write_text(s, encoding="utf-8")

# ─── 5. Create notifications app ───────────────────────────────────────
if not (ROOT / "notifications").exists():
    sh(PY, "manage.py", "startapp", "notifications")

# ─── 6. notifications/tasks.py ─────────────────────────────────────────
write("notifications/tasks.py", '''\
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

from common.context import db_tenant_context
from lab.models import LabResult
from billing.models import InsuranceClaim

logger = logging.getLogger(__name__)


@shared_task
def notify_doctor_lab_result_ready(lab_result_id: int):
    """Email the attending doctor when a lab result is finalized."""
    try:
        # Fetch without tenant filter to find the row
        result = LabResult.all_objects.select_related(
            "lab_order__visit__attending_doctor",
            "lab_order__visit__patient",
            "lab_order__test",
            "tenant"
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

    # RLS Safety: Force tenant context for any nested ORM queries
    with db_tenant_context(result.tenant):
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor.email],
            fail_silently=False,
        )
    return f"Emailed lab result to {doctor.email}"


@shared_task
def notify_receptionist_claim_approved(claim_id: int):
    """Email the admin/reception team when an insurance claim is approved."""
    try:
        claim = InsuranceClaim.all_objects.select_related(
            "invoice__patient", "tenant"
        ).get(id=claim_id)
    except InsuranceClaim.DoesNotExist:
        return f"Claim {claim_id} not found"

    patient = claim.invoice.patient
    provider = claim.patient_insurance.provider.name
    amount = claim.amount_approved or 0.00

    subject = f"[OPD] Claim Approved: {provider} for {patient.full_name}"
    message = (
        f"Good news,\\n\\n"
        f"The claim #{claim.claim_no} submitted to {provider} for {patient.full_name} "
        f"has been APPROVED.\\n"
        f"Approved Amount: {amount} {claim.invoice.currency}\\n\\n"
        f"Please log in to process the final settlement."
    )

    # In a real app, you'd fetch a specific receptionist email.
    # For this demo, we'll send it to the tenant admin.
    with db_tenant_context(claim.tenant):
        from tenants.models import User
        recipient = User.objects.filter(
            tenant=claim.tenant, role="admin", is_active=True
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
''')

# ─── 7. notifications/signals.py ───────────────────────────────────────
write("notifications/signals.py", '''\
from django.db.models.signals import post_save
from django.dispatch import receiver

from lab.models import LabResult
from billing.models import InsuranceClaim
from .tasks import notify_doctor_lab_result_ready, notify_receptionist_claim_approved


@receiver(post_save, sender=LabResult)
def trigger_lab_notification(sender, instance, created, **kwargs):
    if created:
        # Fire and forget to Celery
        notify_doctor_lab_result_ready.delay(instance.id)


@receiver(post_save, sender=InsuranceClaim)
def trigger_claim_notification(sender, instance, created, **kwargs):
    # Trigger only when status changes to APPROVED
    if not created and instance.status == InsuranceClaim.Status.APPROVED:
        # Check if it was just approved by looking at the DB (avoids double-emailing on save)
        # For simplicity, we just fire it. (A real app might use django-fsm or track previous state).
        notify_receptionist_claim_approved.delay(instance.id)
''')

# ─── 8. notifications/apps.py ──────────────────────────────────────────
write("notifications/apps.py", '''\
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        import notifications.signals  # noqa: F401
''')

# ─── 9. Register app in settings ───────────────────────────────────────
print("==> Patching config/settings.py (INSTALLED_APPS)")
s = sp.read_text(encoding="utf-8")
if '"notifications",' not in s:
    s = s.replace('"billing",', '"billing",\n    "notifications.apps.NotificationsConfig",')
    sp.write_text(s, encoding="utf-8")

# ─── 10. Check ─────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. To test, you need TWO terminals:")
print("    T1: celery -A config worker -l info --pool=solo")
print("    T2: python manage.py runserver")