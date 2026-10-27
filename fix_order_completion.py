#!/usr/bin/env python3
"""
fix_order_completion.py -- Mark the parent Order as COMPLETED when Lab/Rad/Pharmacy finish.
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

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# ─── 1. Fix LabOrder completion ────────────────────────────────────────
old_lab = '''        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''
new_lab = '''        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        # Mark the parent order as completed
        lo.order.status = Order.Status.COMPLETED
        lo.order.save(update_fields=["status"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''

if old_lab in v:
    v = v.replace(old_lab, new_lab)
    print("   patched LabOrder completion logic")

# ─── 2. Fix Radiology completion ───────────────────────────────────────
old_rad = '''        ser.save(
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
        
        # Mark the parent order as completed
        ro.order.status = Order.Status.COMPLETED
        ro.order.save(update_fields=["status"])
        
        return Response(ser.data)'''

if old_rad in v:
    v = v.replace(old_rad, new_rad)
    print("   patched Radiology completion logic")

# ─── 3. Fix Pharmacy completion ────────────────────────────────────────
old_pharm = '''            po.status = PharmacyOrder.Status.DISPENSED
            po.dispensed_by = request.user
            po.dispensed_at = timezone.now()
            po.save(update_fields=["status", "dispensed_by", "dispensed_at"])
        return Response(PharmacyOrderSerializer(po).data)'''
new_pharm = '''            po.status = PharmacyOrder.Status.DISPENSED
            po.dispensed_by = request.user
            po.dispensed_at = timezone.now()
            po.save(update_fields=["status", "dispensed_by", "dispensed_at"])
            
            # Mark the parent order as completed
            po.order.status = Order.Status.COMPLETED
            po.order.save(update_fields=["status"])
            
        return Response(PharmacyOrderSerializer(po).data)'''

if old_pharm in v:
    v = v.replace(old_pharm, new_pharm)
    print("   patched Pharmacy completion logic")

vp.write_text(v, encoding="utf-8")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Done. You MUST restart the Django server.")