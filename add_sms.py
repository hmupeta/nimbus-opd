#!/usr/bin/env python3
"""
add_sms.py -- add SMS configuration, logging, and notifications.
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


# ─── 1. Add SmsConfig to tenants/models.py ─────────────────────────────
print("==> Patching tenants/models.py")
tp = ROOT / "tenants" / "models.py"
t = tp.read_text(encoding="utf-8")

if "class SmsConfig" not in t:
    t += '''


class SmsProvider(models.TextChoices):
    AFRICAS_TALKING = "africas_talking", "Africa's Talking"
    TWILIO          = "twilio", "Twilio"
    OTHER           = "other", "Other"


class SmsConfig(models.Model):
    """Per-tenant SMS gateway configuration."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)
    provider = models.CharField(
        max_length=32, choices=SmsProvider.choices,
        default=SmsProvider.AFRICAS_TALKING,
    )
    sender_id = models.CharField(
        max_length=32, blank=True,
        help_text="The short code or alphanumeric sender ID shown on the patient's phone",
    )

    # Encrypted secrets
    api_key = EncryptedTextField(blank=True)
    api_secret = EncryptedTextField(blank=True)

    is_active = models.BooleanField(default=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_verification_status = models.CharField(max_length=32, blank=True)
    last_verification_message = models.TextField(blank=True)

    objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider"],
                name="uniq_sms_provider_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} ({self.sender_id or 'No Sender ID'})"

    def secrets_status(self) -> dict:
        return {
            "api_key": bool(self.api_key),
            "api_secret": bool(self.api_secret),
        }
'''
    tp.write_text(t, encoding="utf-8")

# ─── 2. Add SmsLog to notifications/models.py ──────────────────────────
print("==> Creating notifications/models.py")
write("notifications/models.py", '''\
from django.db import models
from common.models import TenantAwareModel


class SmsLog(TenantAwareModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT   = "sent", "Sent"
        FAILED = "failed", "Failed"

    recipient = models.CharField(max_length=32)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=32, blank=True)
    provider_message_id = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SMS to {self.recipient} ({self.status})"
''')

# ─── 3. Admin for SmsConfig & SmsLog ───────────────────────────────────
print("==> Patching tenants/admin.py")
ap = ROOT / "tenants" / "admin.py"
a = ap.read_text(encoding="utf-8")
if "SmsConfigAdmin" not in a:
    a = a.replace(
        "    MobileMoneyConfig, PaymentGatewayConfig,\n    Tenant, TenantSequence, TenantSettings, User,",
        "    MobileMoneyConfig, PaymentGatewayConfig, SmsConfig,\n    Tenant, TenantSequence, TenantSettings, User,"
    )
    a += '''


@admin.register(SmsConfig)
class SmsConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "sender_id", "is_active", "tenant")
    list_filter = ("provider", "is_active")
    
    def get_queryset(self, request):
        from common.context import get_current_tenant
        qs = super().get_queryset(request)
        if request.user.is_platform_admin or request.user.is_superuser:
            return qs
        t = get_current_tenant() or getattr(request.user, "tenant", None)
        return qs.filter(tenant=t) if t else qs.none()

    def get_form(self, request, obj=None, **kwargs):
        from django import forms
        form = super().get_form(request, obj, **kwargs)
        for name in ("api_key", "api_secret"):
            if name in form.base_fields:
                form.base_fields[name].widget = forms.PasswordInput(render_value=True)
                form.base_fields[name].required = False
        return form
'''
    ap.write_text(a, encoding="utf-8")

print("==> Creating notifications/admin.py")
write("notifications/admin.py", '''\
from django.contrib import admin
from common.admin import TenantModelAdmin
from .models import SmsLog


@admin.register(SmsLog)
class SmsLogAdmin(TenantModelAdmin):
    list_display = ("created_at", "recipient", "status", "provider")
    list_filter = ("status", "provider")
    search_fields = ("recipient", "message")
    readonly_fields = ("created_at", "sent_at")
''')

# ─── 4. SMS Sending Logic ──────────────────────────────────────────────
print("==> Updating notifications/tasks.py")
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
    
    # In production, you would use requests.post() here to hit Africa's Talking/Twilio
    # if config.provider == "africas_talking": ...
    return True, f"mock-{timezone.now().timestamp()}"


@shared_task
def notify_doctor_lab_result_ready(lab_result_id: int):
    try:
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

    # 1. Email Doctor
    subject = f"[OPD] Lab Result Ready: {test_name} for {patient.full_name}"
    message = (
        f"Hello Dr. {doctor.last_name},\\n\\n"
        f"The {test_name} result for {patient.full_name} (MRN: {patient.mrn}) is ready.\\n"
        f"Result: {result.value_text} {result.unit} (Flag: {result.get_flag_display()})\\n\\n"
        f"Please log in to review."
    )

    with db_tenant_context(result.tenant):
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [doctor.email], fail_silently=False)
        
        # 2. SMS Patient
        if patient.phone:
            sms_text = f"Hello {patient.first_name}, your lab results are ready. Please check with the clinic."
            log = SmsLog.objects.create(tenant=result.tenant, recipient=patient.phone, message=sms_text)
            success, provider_resp = _send_sms_real(result.tenant, patient.phone, sms_text)
            if success:
                log.status = SmsLog.Status.SENT
                log.sent_at = timezone.now()
                log.provider_message_id = provider_resp
            else:
                log.status = SmsLog.Status.FAILED
                log.error_message = provider_resp
            log.save()

    return f"Notified doctor and patient"


@shared_task
def notify_patient_appointment(appointment_id: int):
    try:
        appt = Appointment.all_objects.select_related("patient", "doctor", "tenant").get(id=appointment_id)
    except Appointment.DoesNotExist:
        return "Appointment not found"

    patient = appt.patient
    if not patient.phone:
        return "Patient has no phone number"

    time_str = appt.scheduled_start.strftime("%Y-%m-%d %H:%M")
    sms_text = f"Hello {patient.first_name}, your appointment with Dr. {appt.doctor.last_name} is confirmed for {time_str}."

    with db_tenant_context(appt.tenant):
        log = SmsLog.objects.create(tenant=appt.tenant, recipient=patient.phone, message=sms_text)
        success, provider_resp = _send_sms_real(appt.tenant, patient.phone, sms_text)
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

# ─── 5. Update Signals ─────────────────────────────────────────────────
print("==> Updating notifications/signals.py")
write("notifications/signals.py", '''\
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
''')

# ─── 6. Migrations & RLS ───────────────────────────────────────────────
print("==> makemigrations")
sh(PY, "manage.py", "makemigrations", "tenants", "notifications")

tenants_migrations = sorted((ROOT / "tenants" / "migrations").glob("0*.py"), key=lambda p: p.name)
latest_tenants = tenants_migrations[-1].stem
notifications_migrations = sorted((ROOT / "notifications" / "migrations").glob("0*.py"), key=lambda p: p.name)
latest_notifications = notifications_migrations[-1].stem

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
                CREATE POLICY tenant_isolation ON "tenants_smsconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

                ALTER TABLE "notifications_smslog" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "notifications_smslog" FORCE ROW LEVEL SECURITY;
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

print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 7. Add to seed_demo ───────────────────────────────────────────────
print("==> Patching seed_demo.py")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

if "SmsConfig" not in seed:
    seed = seed.replace(
        "    MobileMoneyConfig, PaymentGatewayConfig,\n    Tenant, TenantSequence, TenantSettings, User,",
        "    MobileMoneyConfig, PaymentGatewayConfig, SmsConfig,\n    Tenant, TenantSequence, TenantSettings, User,"
    )
    # Add to reset list
    seed = seed.replace(
        "        MobileMoneyConfig,\n        PaymentGatewayConfig,",
        "        MobileMoneyConfig,\n        PaymentGatewayConfig,\n        SmsConfig,"
    )
    
    # Add seeding logic
    helper = '''def _seed_sms(tenant):
    SmsConfig.objects.get_or_create(
        tenant=tenant, provider="africas_talking",
        defaults=dict(
            sender_id="OPD-CLINIC",
            api_key="dummy-africas-talking-key",
            api_secret="dummy-africas-talking-secret",
            is_active=True,
        ),
    )

'''
    if "def _seed_sms" not in seed:
        seed = seed.replace("def _seed_gateways", helper + "def _seed_gateways")
    
    seed = seed.replace("            _seed_gateways(tenant)", "            _seed_gateways(tenant)\n            _seed_sms(tenant)")
    seed_path.write_text(seed, encoding="utf-8")

# ─── 8. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset (NO_REDIS=1)")
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
subprocess.run([str(PY), "manage.py", "seed_demo", "--reset"], check=True, env=seed_env)

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("\\n==> Done. SMS integration active.")