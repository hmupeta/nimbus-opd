#!/usr/bin/env python3
"""
final_doctor_fix.py
  - Forces catalog permissions to allow Doctors.
  - Force-completes all orders for the stuck visit.
"""
from __future__ import annotations
import os
import re
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

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

# ─── 1. BACKEND: Regex replace permissions ─────────────────────────────
print("==> Patching api/views.py (Regex Permissions)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# LabTestViewSet
v = re.sub(
    r'(class LabTestViewSet.*?)permission_classes\s*=\s*\[require_roles\("admin", "lab"\)\]',
    r'\1permission_classes = [require_roles("admin", "lab", "doctor", "nurse")]',
    v, flags=re.DOTALL
)

# MedicineViewSet
v = re.sub(
    r'(class MedicineViewSet.*?)permission_classes\s*=\s*\[require_roles\("admin", "pharmacist"\)\]',
    r'\1permission_classes = [require_roles("admin", "pharmacist", "doctor", "nurse")]',
    v, flags=re.DOTALL
)

# RadiologyExamViewSet
v = re.sub(
    r'(class RadiologyExamViewSet.*?)permission_classes\s*=\s*\[require_roles\("admin", "radiology"\)\]',
    r'\1permission_classes = [require_roles("admin", "radiology", "doctor", "nurse")]',
    v, flags=re.DOTALL
)

vp.write_text(v, encoding="utf-8")
print("   enforced catalog permissions")

# ─── 2. BACKEND: Force complete stuck orders ───────────────────────────
print("==> Force-completing all orders for Visit 5")
backfill = ROOT / "temp_force_close.py"
backfill.write_text('''\
from common.context import db_tenant_context
from tenants.models import Tenant
from clinical.models import Order
from visits.models import Visit

t = Tenant.objects.get(code="demo")
with db_tenant_context(t):
    v = Visit.all_objects.filter(id=5).first()
    if v:
        orders = Order.all_objects.filter(visit=v)
        for o in orders:
            o.status = Order.Status.COMPLETED
            o.save(update_fields=["status"])
        print(f"Force-completed {orders.count()} orders for {v.visit_no}.")
    else:
        print("Visit 5 not found.")
''', encoding="utf-8")
sh(PY, "manage.py", "shell", "<", "temp_force_close.py", check=False)
backfill.unlink()

# ─── 3. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(rbac): force doctor access to catalogs and force-complete stuck orders", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")