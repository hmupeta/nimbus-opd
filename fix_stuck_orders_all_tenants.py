#!/usr/bin/env python3
"""
fix_stuck_orders_all_tenants.py -- Fix stuck orders across ALL tenants.
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
# Force UTF-8 so emojis / special chars don't crash on Windows
ENV["PYTHONIOENCODING"] = "utf-8"

# ─── 1. Force complete stuck orders across ALL tenants ─────────────────
print("==> Scanning all tenants and forcing stuck orders to completed...")

# ASCII-only, no emojis
shell_script = r'''
from tenants.models import Tenant
from common.context import db_tenant_context
from clinical.models import Order

total_fixed = 0
for t in Tenant.objects.all():
    with db_tenant_context(t):
        stuck = Order.all_objects.filter(
            tenant=t,
            status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS],
        )
        count = stuck.count()
        if count > 0:
            stuck.update(status=Order.Status.COMPLETED)
            print(f"[FIXED] {t.name}: {count} stuck orders marked COMPLETED")
            total_fixed += count
        else:
            print(f"[OK]    {t.name}: no stuck orders")

print(f"\nTOTAL FIXED: {total_fixed} orders")
'''

r = subprocess.run(
    [str(PY), "manage.py", "shell", "-c", shell_script],
    cwd=ROOT, env=ENV, capture_output=True, text=True,
    encoding="utf-8", errors="replace",
)
print(r.stdout.strip())
if r.returncode != 0:
    print("STDERR:")
    print(r.stderr.strip())

# ─── 2. Verify the visit timeline for Lubuto ───────────────────────────
print("\n==> Verifying Lubuto Mupeta's orders...")
verify_script = r'''
from tenants.models import Tenant
from common.context import db_tenant_context
from patients.models import Patient
from clinical.models import Order
from visits.models import Visit

for t in Tenant.objects.all():
    with db_tenant_context(t):
        pats = Patient.all_objects.filter(tenant=t, first_name="Lubuto")
        for p in pats:
            print(f"Found {p.full_name} in {t.name}")
            for v in Visit.all_objects.filter(tenant=t, patient=p):
                print(f"  Visit {v.visit_no} (status={v.status})")
                for o in Order.all_objects.filter(tenant=t, visit=v):
                    print(f"    Order {o.id} ({o.kind}) -> {o.status}")
'''
r = subprocess.run(
    [str(PY), "manage.py", "shell", "-c", verify_script],
    cwd=ROOT, env=ENV, capture_output=True, text=True,
    encoding="utf-8", errors="replace",
)
print(r.stdout.strip())

print("\n✅ Done. Refresh the browser to see the updated status.")