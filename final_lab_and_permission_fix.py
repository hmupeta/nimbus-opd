#!/usr/bin/env python3
"""
final_lab_and_permission_fix.py
  - Allows Doctors/Nurses to READ lab, radiology, and medicine catalogs.
  - Force-completes any parent Order that has a result/dispensation.
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

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

# ─── 1. BACKEND: Restore Read Permissions for Catalogs ─────────────────
print("==> Patching api/views.py (Catalog Read Permissions)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Allow Doctors/Nurses to view Lab Tests
v = v.replace(
    'class LabTestViewSet(TenantScopedViewSet):\n    serializer_class = LabTestSerializer\n    queryset = LabTest.objects.all()\n    permission_classes = [require_roles("admin", "lab")]',
    'class LabTestViewSet(TenantScopedViewSet):\n    serializer_class = LabTestSerializer\n    queryset = LabTest.objects.all()\n    permission_classes = [require_roles("admin", "lab", "doctor", "nurse")]'
)

# Allow Doctors/Nurses to view Radiology Exams
v = v.replace(
    'class RadiologyExamViewSet(TenantScopedViewSet):\n    serializer_class = RadiologyExamSerializer\n    permission_classes = [require_roles("admin", "radiology")]',
    'class RadiologyExamViewSet(TenantScopedViewSet):\n    serializer_class = RadiologyExamSerializer\n    permission_classes = [require_roles("admin", "radiology", "doctor", "nurse")]'
)

# Allow Doctors/Nurses to view Medicines
v = v.replace(
    'class MedicineViewSet(TenantScopedViewSet):\n    serializer_class = MedicineSerializer\n    queryset = Medicine.objects.all()\n    permission_classes = [require_roles("admin", "pharmacist")]',
    'class MedicineViewSet(TenantScopedViewSet):\n    serializer_class = MedicineSerializer\n    queryset = Medicine.objects.all()\n    permission_classes = [require_roles("admin", "pharmacist", "doctor", "nurse")]'
)

vp.write_text(v, encoding="utf-8")
print("   updated catalog permissions")

# ─── 2. DATABASE: Force Complete Stuck Orders ──────────────────────────
print("==> Force-completing stuck orders based on existing results")
backfill = ROOT / "temp_force_complete.py"
backfill.write_text('''\
from common.context import db_tenant_context
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder, LabResult
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder

for t in Tenant.objects.all():
    with db_tenant_context(t):
        pending = Order.all_objects.filter(tenant=t, status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS])
        fixed = 0
        for order in pending:
            completed = False
            if order.kind == "lab":
                # If ANY lab result exists for this order, mark it completed
                subs = LabOrder.all_objects.filter(order=order)
                if LabResult.all_objects.filter(lab_order__in=subs).exists():
                    completed = True
            elif order.kind == "radiology":
                subs = RadiologyOrder.all_objects.filter(order=order)
                if all(s.status == "reported" for s in subs) and subs.exists():
                    completed = True
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.all_objects.filter(order=order)
                if all(s.status == "dispensed" for s in subs) and subs.exists():
                    completed = True
            
            if completed:
                order.status = Order.Status.COMPLETED
                order.save(update_fields=["status"])
                fixed += 1
                print(f"  FIXED: Order {order.id} ({order.kind}) is now COMPLETED.")
        
        print(f"Checked {t.name}. Fixed {fixed} orders.")
''', encoding="utf-8")
sh(PY, "manage.py", "shell", "<", "temp_force_complete.py", check=False)
backfill.unlink()

# ─── 3. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(rbac): allow doctors to read catalogs; force-complete stuck orders with results", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")