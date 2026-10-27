#!/usr/bin/env python3
"""
sync_stuck_orders.py -- Force sync parent Order status based on sub-orders.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")

# We use a heredoc-style script via the shell command to avoid file writing issues
script = """
from common.context import db_tenant_context
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder

for t in Tenant.objects.all():
    with db_tenant_context(t):
        open_orders = Order.objects.filter(status__in=['pending', 'in_progress'])
        print(f"Checking {open_orders.count()} open orders for {t.name}...")
        
        for order in open_orders:
            if order.kind == "lab":
                subs = LabOrder.objects.filter(order=order)
                if subs.exists() and all(s.status in ["completed", "cancelled"] for s in subs):
                    order.status = "completed"
                    order.save(update_fields=["status"])
                    print(f"  Fixed Lab Order {order.id}")
                    
            elif order.kind == "radiology":
                subs = RadiologyOrder.objects.filter(order=order)
                if subs.exists() and all(s.status in ["reported", "cancelled"] for s in subs):
                    order.status = "completed"
                    order.save(update_fields=["status"])
                    print(f"  Fixed Radiology Order {order.id}")
                    
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.objects.filter(order=order)
                if subs.exists() and all(s.status in ["dispensed", "cancelled"] for s in subs):
                    order.status = "completed"
                    order.save(update_fields=["status"])
                    print(f"  Fixed Pharmacy Order {order.id}")
                    
print("Done. You can now close the visits.")
"""

print("==> Forcing database sync...")
subprocess.run([str(PY), "manage.py", "shell", "-c", script], check=True)