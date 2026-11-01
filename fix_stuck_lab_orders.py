#!/usr/bin/env python3
"""
fix_stuck_lab_orders.py
  - Re-adds parent Order sync to Lab/Rad/Pharmacy actions.
  - Fixes clinical AppConfig in settings.py.
  - Backfills the currently stuck orders.
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

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. BACKEND: Restore Parent Order Updates in API ───────────────────
print("==> Patching api/views.py (Restoring parent order sync)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# 1a. Lab Result
old_lab = '''        # Update the parent LabOrder status
        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''
new_lab = '''        # Update the parent LabOrder status
        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        # Update the parent Order status
        lo.order.status = Order.Status.COMPLETED
        lo.order.save(update_fields=["status"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''
if old_lab in v:
    v = v.replace(old_lab, new_lab)
    print("   patched LabOrder.result")

# 1b. Radiology Report
old_rad = '''        ro = ser.save(
            radiologist=request.user,
            status=RadiologyOrder.Status.REPORTED,
            reported_at=timezone.now(),
        )
        
        return Response(ser.data)'''
new_rad = '''        ro = ser.save(
            radiologist=request.user,
            status=RadiologyOrder.Status.REPORTED,
            reported_at=timezone.now(),
        )
        
        # Update the parent Order status
        ro.order.status = Order.Status.COMPLETED
        ro.order.save(update_fields=["status"])
        
        return Response(ser.data)'''
if old_rad in v:
    v = v.replace(old_rad, new_rad)
    print("   patched RadiologyOrder.report")

# 1c. Pharmacy Dispense
old_pharm = '''            po.status = PharmacyOrder.Status.DISPENSED
            po.dispensed_by = request.user
            po.dispensed_at = timezone.now()
            po.save(update_fields=["status", "dispensed_by", "dispensed_at"])
            
        return Response(PharmacyOrderSerializer(po).data)'''
new_pharm = '''            po.status = PharmacyOrder.Status.DISPENSED
            po.dispensed_by = request.user
            po.dispensed_at = timezone.now()
            po.save(update_fields=["status", "dispensed_by", "dispensed_at"])
            
            # Update the parent Order status
            po.order.status = Order.Status.COMPLETED
            po.order.save(update_fields=["status"])
            
        return Response(PharmacyOrderSerializer(po).data)'''
if old_pharm in v:
    v = v.replace(old_pharm, new_pharm)
    print("   patched PharmacyOrder.dispense")

vp.write_text(v, encoding="utf-8")

# ─── 2. BACKEND: Ensure ClinicalAppConfig is used ──────────────────────
print("==> Patching config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if '"clinical.apps.ClinicalConfig"' not in s:
    s = s.replace('"clinical",', '"clinical.apps.ClinicalConfig",')
    sp.write_text(s, encoding="utf-8")
    print("   registered clinical.apps.ClinicalConfig")

# ─── 3. BACKEND: Backfill Existing Stuck Orders ────────────────────────
print("==> Backfilling stuck orders")
backfill = ROOT / "temp_backfill.py"
backfill.write_text('''\
from common.context import db_tenant_context
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder

for t in Tenant.objects.all():
    with db_tenant_context(t):
        pending = Order.all_objects.filter(tenant=t, status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS])
        fixed = 0
        for order in pending:
            if order.kind == "lab":
                subs = LabOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["completed", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    fixed += 1
            elif order.kind == "radiology":
                subs = RadiologyOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["reported", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    fixed += 1
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["dispensed", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    fixed += 1
        print(f"{t.name}: Fixed {fixed} stuck parent orders.")
''', encoding="utf-8")
sh(PY, "manage.py", "shell", "<", "temp_backfill.py", check=False)
backfill.unlink()

# ─── 4. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(clinical): restore parent order sync in API and register ClinicalConfig", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")