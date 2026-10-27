#!/usr/bin/env python3
"""
fix_audit_signals.py -- fix FK serialization and transaction safety in audit signals.
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


# ─── 1. Rewrite audit/signals.py ───────────────────────────────────────
write("audit/signals.py", '''\
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from common.context import get_current_ip, get_current_tenant, get_current_user
from common.models import TenantAwareModel

from .models import AuditLog

logger = logging.getLogger(__name__)


def serialize_instance(instance):
    """Convert a model instance to a JSON-safe dict, redacting sensitive fields."""
    if instance is None:
        return None
    data = {}
    for field in instance._meta.fields:
        # For relational fields, field.attname gives the *_id column (JSON-safe).
        # For scalar fields, attname == name, so this works universally.
        try:
            val = getattr(instance, field.attname)
        except Exception:
            val = None

        if field.name == "password":
            val = "<redacted>"
        elif hasattr(val, "isoformat"):       # datetime / date / time
            val = val.isoformat()
        elif hasattr(val, "hex"):             # UUID
            val = str(val)
        data[field.name] = val
    return data


def log_action(instance, action, before, after):
    if isinstance(instance, AuditLog):
        return  # Prevent infinite recursion
    if not isinstance(instance, TenantAwareModel):
        return

    tenant = get_current_tenant() or getattr(instance, "tenant", None)
    if not tenant:
        return  # Cannot log without a tenant

    user = get_current_user()
    if user and not user.is_authenticated:
        user = None

    try:
        # Isolate audit writes in a savepoint so a failure can NEVER poison
        # the outer transaction. If this raises, PostgreSQL rolls back just
        # this block and the surrounding request/business logic continues.
        with transaction.atomic():
            AuditLog.all_objects.create(
                tenant=tenant,
                user=user,
                action=action,
                content_type=ContentType.objects.get_for_model(instance),
                object_id=str(instance.pk),
                before=before,
                after=after,
                ip=get_current_ip(),
            )
    except Exception as e:
        logger.error(f"Failed to write audit log for {instance}: {e}")


@receiver(pre_save)
def pre_save_handler(sender, instance, **kwargs):
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    if not instance.pk:
        instance._audit_before = None
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
        instance._audit_before = serialize_instance(old)
    except sender.DoesNotExist:
        instance._audit_before = None


@receiver(post_save)
def post_save_handler(sender, instance, created, **kwargs):
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    if created:
        log_action(instance, "create", None, serialize_instance(instance))
    else:
        before = getattr(instance, "_audit_before", None)
        after = serialize_instance(instance)
        if before != after:
            log_action(instance, "update", before, after)


@receiver(pre_delete)
def pre_delete_handler(sender, instance, **kwargs):
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    log_action(instance, "delete", serialize_instance(instance), None)
''')

# ─── 2. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

# ─── 3. Sanity check ───────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Verify audit trail:")
print("    python manage.py shell -c \\\"from audit.models import AuditLog; print('logs:', AuditLog.objects.count())\\\"")