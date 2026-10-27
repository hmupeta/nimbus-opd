#!/usr/bin/env python3
"""
clean_stuck_orders.py -- Sync parent Order status based on sub-orders.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

script = '''
from common.context import db_tenant_context
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder

for t in Tenant.objects.all():
    with db_tenant_context(t):
        open_orders = Order.objects.filter(status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS])
        print(f"Checking {open_orders.count()} open orders for {t.name}...")
        
        for order in open_orders:
            if order.kind == "lab":
                subs = LabOrder.objects.filter(order=order)
                if all(s.status in ["completed", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    print(f"  Fixed Lab Order {order.id}")
                    
            elif order.kind == "radiology":
                subs = RadiologyOrder.objects.filter(order=order)
                if all(s.status in ["reported", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    print(f"  Fixed Radiology Order {order.id}")
                    
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.objects.filter(order=order)
                if all(s.status in ["dispensed", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    print(f"  Fixed Pharmacy Order {order.id}")
                    
        print("Done. You can now close the visits.")
'''

# Write to a temp file to run via manage.py shell
temp_path = ROOT / "temp_clean.py"
temp_path.write_text(script, encoding="utf-8")

subprocess.run([str(PY), "manage.py", "shell", "<", str(temp_path)], shell=True, env=ENV)
temp_path.unlink()