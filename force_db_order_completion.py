#!/usr/bin/env python3
"""
force_db_order_completion.py
  - Directly queries and updates the specific stuck order for Visit 5.
  - Verifies the API endpoint logic is correct.
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

# ─── 1. Force Complete the specific order in the DB ────────────────────
print("==> Forcing DB update for Visit 5...")
shell_script = '''
from tenants.models import Tenant
from common.context import db_tenant_context
from visits.models import Visit
from clinical.models import Order

t = Tenant.objects.get(code="demo")
with db_tenant_context(t):
    v = Visit.all_objects.filter(id=5).first()
    if v:
        orders = Order.all_objects.filter(visit=v)
        count = 0
        for o in orders:
            o.status = Order.Status.COMPLETED
            o.save(update_fields=["status"])
            count += 1
        print(f"✅ Successfully marked {count} orders for {v.visit_no} as COMPLETED.")
    else:
        print("❌ Visit 5 not found.")
'''

r = subprocess.run([str(PY), "manage.py", "shell", "-c", shell_script], cwd=ROOT, env=ENV, capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())

# ─── 2. Check the API View logic just in case ──────────────────────────
print("\n==> Checking API logic (LabOrderViewSet.result)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "lo.order.status = Order.Status.COMPLETED" not in v:
    print("   ⚠️ API is missing the parent order update! Patching now...")
    old_lab = '''        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''
    new_lab = '''        lo.status = LabOrder.Status.COMPLETED
        lo.completed_at = timezone.now()
        lo.save(update_fields=["status", "completed_at"])
        
        lo.order.status = Order.Status.COMPLETED
        lo.order.save(update_fields=["status"])
        
        return Response(LabResultSerializer(result).data, status=status.HTTP_200_OK)'''
    
    if old_lab in v:
        v = v.replace(old_lab, new_lab)
        vp.write_text(v, encoding="utf-8")
        print("   ✅ Patched API view.")
else:
    print("   ✅ API logic is already correct.")

# ─── 3. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(db): force complete stuck orders via shell script", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Done. Restart the backend to pick up any API changes, then refresh the page.")