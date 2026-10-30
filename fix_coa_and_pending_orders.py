#!/usr/bin/env python3
"""
fix_coa_and_pending_orders.py
  - Adds COA seeding back into seed_demo.py (so it runs on every deploy).
  - Backfills existing tenants with COA.
  - Backfills existing pending Orders to completed if their sub-tasks are done.
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

def sh(*cmd, check=True, shell=False):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True, shell=shell)

# ─── 1. Add COA to seed_demo.py ────────────────────────────────────────
print("==> Updating seed_demo.py to seed Chart of Accounts")
seed = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
s = seed.read_text(encoding="utf-8")

if "ChartOfAccount" not in s:
    # Add import
    s = s.replace(
        "from patients.models import Patient",
        "from patients.models import Patient\nfrom accounting.models import ChartOfAccount"
    )
    # Add seeding logic right after the tenant context opens in _seed_demo
    old_context = "        with db_tenant_context(tenant):\n            users = self._demo_users(tenant)"
    new_context = """        with db_tenant_context(tenant):
            # Seed Standard COA
            accounts = [
                ("1000", "Cash & Bank", "asset"), ("1100", "Accounts Receivable", "asset"),
                ("1200", "Inventory", "asset"), ("1500", "Fixed Assets", "asset"),
                ("2000", "Accounts Payable", "liability"), ("3000", "Owner's Equity", "equity"),
                ("4000", "Consultation Revenue", "revenue"), ("4100", "Pharmacy Revenue", "revenue"),
                ("4200", "Lab Revenue", "revenue"), ("4300", "Radiology Revenue", "revenue"),
                ("5000", "Salaries & Wages", "expense"), ("5100", "Rent Expense", "expense"),
                ("5200", "Utilities Expense", "expense"), ("5300", "Medical Supplies", "expense"),
            ]
            for code, name, type in accounts:
                ChartOfAccount.all_objects.get_or_create(
                    tenant=tenant, code=code, defaults={"name": name, "type": type}
                )

            users = self._demo_users(tenant)"""
    s = s.replace(old_context, new_context)
    seed.write_text(s, encoding="utf-8")
    print("   patched seed_demo.py")

# ─── 2. Create a one-off backfill script ───────────────────────────────
print("==> Writing backfill script")
backfill_script = ROOT / "temp_backfill.py"
backfill_script.write_text('''\
from tenants.models import Tenant
from accounting.utils import seed_default_coa
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder
from common.context import db_tenant_context

for t in Tenant.objects.all():
    with db_tenant_context(t):
        # 1. Backfill COA
        seed_default_coa(t)
        
        # 2. Backfill Orders
        pending_orders = Order.all_objects.filter(tenant=t, status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS])
        fixed_count = 0
        for order in pending_orders:
            if order.kind == "lab":
                subs = LabOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["completed", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    fixed_count += 1
            elif order.kind == "radiology":
                subs = RadiologyOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["reported", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    fixed_count += 1
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["dispensed", "cancelled"] for s in subs):
                    order.status = Order.Status.COMPLETED
                    order.save(update_fields=["status"])
                    fixed_count += 1
                    
        print(f"{t.name}: Seeded COA. Fixed {fixed_count} stuck orders.")
''', encoding="utf-8")

# ─── 3. Run the backfill script ────────────────────────────────────────
print("\n==> Running backfill script")
sh(PY, "manage.py", "shell", "<", "temp_backfill.py", shell=True)
backfill_script.unlink() # Delete after use

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(data): seed COA on deploy and backfill stuck parent orders", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")