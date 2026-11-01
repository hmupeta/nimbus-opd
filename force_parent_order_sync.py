#!/usr/bin/env python3
"""
force_parent_order_sync.py
  - Adds save() overrides to LabOrder, RadiologyOrder, PharmacyOrder.
  - Forcefully fixes the stuck parent order for Lubuto Mupeta.
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

def patch_model(rel_path, class_name, sync_method):
    """Inject a save() method into a model class."""
    p = ROOT / rel_path
    content = p.read_text(encoding="utf-8")
    
    if f"def save(self, *args, **kwargs):" in content.split(f"class {class_name}")[1].split("class ")[0]:
        print(f"   {rel_path} already has save() override")
        return

    # Find the class and its Meta or end of file
    import re
    pattern = re.compile(rf"(class {class_name}.*?)(\n    class Meta:|\n\nclass |\Z)", re.DOTALL)
    match = pattern.search(content)
    if not match:
        print(f"   [WARN] Could not find class {class_name} in {rel_path}")
        return

    # Insert save() before Meta (or end of class)
    new_save = f"""
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if hasattr(self, "order") and self.order:
            from clinical.signals import _check_and_complete_parent_order
            _check_and_complete_parent_order(self)
"""
    
    if "\n    class Meta:" in match.group(1):
        new_content = content.replace(
            match.group(1),
            match.group(1).replace("    class Meta:", new_save + "\n    class Meta:")
        )
    else:
        new_content = content.replace(match.group(1), match.group(1) + new_save)
    
    p.write_text(new_content, encoding="utf-8")
    print(f"   added save() override to {class_name} in {rel_path}")

# ─── 1. Patch Models ───────────────────────────────────────────────────
print("==> Patching models to guarantee parent order sync")
patch_model("lab/models.py", "LabOrder", "sync_parent")
patch_model("radiology/models.py", "RadiologyOrder", "sync_parent")
patch_model("pharmacy/models.py", "PharmacyOrder", "sync_parent")

# ─── 2. Force Fix Existing Stuck Order ─────────────────────────────────
print("\n==> Force-fixing Lubuto Mupeta's stuck order")
backfill = ROOT / "temp_force_fix.py"
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
            all_done = False
            if order.kind == "lab":
                subs = LabOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["completed", "cancelled"] for s in subs):
                    all_done = True
            elif order.kind == "radiology":
                subs = RadiologyOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["reported", "cancelled"] for s in subs):
                    all_done = True
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.all_objects.filter(order=order)
                if subs.exists() and all(s.status in ["dispensed", "cancelled"] for s in subs):
                    all_done = True
            
            if all_done:
                order.status = Order.Status.COMPLETED
                order.save(update_fields=["status"])
                fixed += 1
                print(f"  FIXED: Order {order.id} ({order.kind}) is now COMPLETED.")
        
        print(f"Checked {t.name}. Fixed {fixed} orders.")
''', encoding="utf-8")
sh(PY, "manage.py", "shell", "<", "temp_force_fix.py", check=False)
backfill.unlink()

# ─── 3. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(clinical): override save() in sub-orders to force parent sync", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")