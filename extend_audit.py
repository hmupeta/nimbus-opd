#!/usr/bin/env python3
"""
extend_audit.py -- add automatic audit logging signals.

Captures CREATE, UPDATE, DELETE across all TenantAwareModel subclasses.
Stores before/after JSON snapshots, user, and IP in audit.AuditLog.
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


# ─── 1. Update common/context.py ───────────────────────────────────────
write("common/context.py", '''\
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import connection, transaction

_current_tenant = ContextVar("current_tenant", default=None)
_current_user = ContextVar("current_user", default=None)
_current_ip = ContextVar("current_ip", default=None)


def set_current_tenant(tenant):
    _current_tenant.set(tenant)


def get_current_tenant():
    return _current_tenant.get()


def clear_current_tenant():
    _current_tenant.set(None)


def set_current_user(user):
    _current_user.set(user)


def get_current_user():
    return _current_user.get()


def set_current_ip(ip):
    _current_ip.set(ip)


def get_current_ip():
    return _current_ip.get()


@contextmanager
def db_tenant_context(tenant):
    """Bind the tenant in memory AND in the DB session (transaction-scoped)."""
    set_current_tenant(tenant)
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    [str(tenant.id)],
                )
            yield
    finally:
        clear_current_tenant()
''')

# ─── 2. Update common/middleware.py ────────────────────────────────────
write("common/middleware.py", '''\
from django.http import HttpResponseForbidden

from .context import (
    db_tenant_context, set_current_ip, set_current_user,
)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        tenant = getattr(user, "tenant", None) if user and user.is_authenticated else None

        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant and (not tenant or str(tenant.id) != header_tenant):
            return HttpResponseForbidden("Tenant mismatch")

        # Set audit context
        set_current_user(user if user and user.is_authenticated else None)
        set_current_ip(request.META.get("REMOTE_ADDR"))

        if tenant is None:
            return self.get_response(request)

        with db_tenant_context(tenant):
            return self.get_response(request)
''')

# ─── 3. Write audit/signals.py ─────────────────────────────────────────
write("audit/signals.py", '''\
import logging

from django.contrib.contenttypes.models import ContentType
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
        val = getattr(instance, field.name)
        if field.name in ("password",):
            val = "<redacted>"
        elif hasattr(val, "isoformat"):
            val = val.isoformat()
        elif hasattr(val, "hex"):  # UUID
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
        # Never let an audit failure crash the actual business logic
        logger.error(f"Failed to write audit log for {instance}: {e}")


@receiver(pre_save)
def pre_save_handler(sender, instance, **kwargs):
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    if not instance.pk:
        instance._audit_before = None
        return
    try:
        # Use all_objects to bypass TenantManager filtering in case context is off
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
        if before != after:  # Only log if something actually changed
            log_action(instance, "update", before, after)


@receiver(pre_delete)
def pre_delete_handler(sender, instance, **kwargs):
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    log_action(instance, "delete", serialize_instance(instance), None)
''')

# ─── 4. Write audit/apps.py ────────────────────────────────────────────
write("audit/apps.py", '''\
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"

    def ready(self):
        # Import signals to register them
        from . import signals  # noqa: F401
''')

# ─── 5. Patch settings.py to use AuditConfig ───────────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if '"audit",' in s:
    s = s.replace('"audit",', '"audit.apps.AuditConfig",')
    sp.write_text(s, encoding="utf-8")
    print("   replaced 'audit' with 'audit.apps.AuditConfig'")

# ─── 6. Run check ──────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. To test, create a patient via the shell or admin.")
print("    Then check: python manage.py shell -c \"from audit.models import AuditLog; print(AuditLog.objects.count())\"")