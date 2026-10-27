#!/usr/bin/env python3
"""
fix_seed_import.py -- rewrite seed_demo.py cleanly (fixes the missing import).
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


# ─── 1. Rewrite seed_demo.py in full ───────────────────────────────────
write("tenants/management/commands/seed_demo.py", '''\
"""
seed_demo -- populate the OPD with a realistic multi-tenant dataset.

Idempotent: re-running on an already-seeded DB is a no-op.
Use --reset to wipe tenant-scoped data and rebuild from scratch.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand

from audit.models import AuditLog
from clinical.models import ClinicalNote, Order, OrderItem
from common.context import db_tenant_context
from lab.models import LabOrder, LabResult, LabTest
from patients.models import Patient
from pharmacy.models import (
    Medicine, PharmacyItem, PharmacyOrder, Stock, StockMovement,
)
from radiology.models import RadiologyOrder
from tenants.models import Tenant, TenantSequence, TenantSettings, User
from visits.models import Visit
from vitals.models import VitalDefinition, Vitals, VitalValue


DEMO_PASSWORD = "demo"


# ── helpers ────────────────────────────────────────────────────────────
def _make_user(tenant, email, role, first, last, *, staff=False, superuser=False):
    user, created = User.objects.get_or_create(
        email=email,
        defaults=dict(
            tenant=tenant, role=role,
            first_name=first, last_name=last,
            is_staff=staff, is_superuser=superuser,
        ),
    )
    if created:
        user.set_password(DEMO_PASSWORD)
        user.save()
    return user


def _reset_tenant(tenant):
    """Delete every tenant-scoped row for this tenant in FK-safe order.

    Must run inside db_tenant_context so RLS lets the DELETEs see the rows.
    AuditLog is deleted LAST because deleting other models triggers
    pre_delete signals that CREATE new AuditLog rows.
    """
    order_of_deletion = [
        StockMovement, Stock,
        PharmacyItem, PharmacyOrder,
        LabResult, LabOrder, RadiologyOrder,
        OrderItem, Order,
        ClinicalNote,
        VitalValue, Vitals, VitalDefinition,
        Visit, Patient,
        LabTest, Medicine,
        TenantSequence,
        TenantSettings,
        User,
        AuditLog,
    ]
    with db_tenant_context(tenant):
        for model in order_of_deletion:
            manager = getattr(model, "all_objects", model.objects)
            manager.filter(tenant=tenant).delete()

        tenant.delete()


# ── command ────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Seed a realistic multi-tenant OPD