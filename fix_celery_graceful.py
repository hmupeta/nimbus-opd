#!/usr/bin/env python3
"""
fix_celery_graceful.py -- prevent Redis connection errors from crashing the app.
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


# ─── 1. Catch connection errors in signals ─────────────────────────────
write("notifications/signals.py", '''\
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from lab.models import LabResult
from billing.models import InsuranceClaim
from .tasks import notify_doctor_lab_result_ready, notify_receptionist_claim_approved

logger = logging.getLogger(__name__)

@receiver(post_save, sender=LabResult)
def trigger_lab_notification(sender, instance, created, **kwargs):
    if created:
        try:
            notify_doctor_lab_result_ready.delay(instance.id)
        except Exception as e:
            # Never let a broker outage crash the main DB transaction
            logger.error(f"Failed to queue lab result notification for {instance}: {e}")

@receiver(post_save, sender=InsuranceClaim)
def trigger_claim_notification(sender, instance, created, **kwargs):
    if not created and instance.status == InsuranceClaim.Status.APPROVED:
        try:
            notify_receptionist_claim_approved.delay(instance.id)
        except Exception as e:
            logger.error(f"Failed to queue claim approval notification for {instance}: {e}")
''')

# ─── 2. Add EAGER mode fallback to settings ────────────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

if "CELERY_TASK_ALWAYS_EAGER" not in s:
    s = s.replace(
        'CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")',
        '# If NO_REDIS=1 is set, run tasks synchronously on the main thread (no Redis needed)\n'
        'CELERY_TASK_ALWAYS_EAGER = os.environ.get("NO_REDIS", "0") == "1"\n'
        'CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")'
    )
    sp.write_text(s, encoding="utf-8")
    print("   patched config/settings.py")

# ─── 3. Run seed_demo again ────────────────────────────────────────────
print("==> seed_demo --reset")
# We set NO_REDIS=1 here to force synchronous execution for the seed
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
subprocess.run([str(PY), "manage.py", "seed_demo", "--reset"], check=True, env=seed_env)

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")
print("    To run normally with emails printing to console (no Redis):")
print("      $env:NO_REDIS='1'; python manage.py runserver")