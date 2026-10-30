#!/usr/bin/env python3
"""
seed_standard_coa.py
  - Creates a utility to seed standard Chart of Accounts.
  - Attaches a signal to auto-seed for new tenants.
  - Backfills existing tenants.
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
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. Create Utility Function ────────────────────────────────────────
print("==> Creating accounting/utils.py")
write("accounting/utils.py", '''\
from accounting.models import ChartOfAccount

def seed_default_coa(tenant):
    """Creates the standard Chart of Accounts for a tenant."""
    accounts = [
        # Assets
        ("1000", "Cash & Bank", "asset"),
        ("1100", "Accounts Receivable", "asset"),
        ("1200", "Inventory", "asset"),
        ("1500", "Fixed Assets", "asset"),
        # Liabilities
        ("2000", "Accounts Payable", "liability"),
        # Equity
        ("3000", "Owner's Equity", "equity"),
        # Revenue
        ("4000", "Consultation Revenue", "revenue"),
        ("4100", "Pharmacy Revenue", "revenue"),
        ("4200", "Lab Revenue", "revenue"),
        ("4300", "Radiology Revenue", "revenue"),
        # Expenses
        ("5000", "Salaries & Wages", "expense"),
        ("5100", "Rent Expense", "expense"),
        ("5200", "Utilities Expense", "expense"),
        ("5300", "Medical Supplies", "expense"),
    ]
    
    for code, name, type in accounts:
        ChartOfAccount.all_objects.get_or_create(
            tenant=tenant,
            code=code,
            defaults={"name": name, "type": type}
        )
''')

# ─── 2. Attach Signal ──────────────────────────────────────────────────
print("==> Patching accounting/signals.py")
sp = ROOT / "accounting" / "signals.py"
s = sp.read_text(encoding="utf-8")

if "seed_default_coa" not in s:
    # Add imports
    s = s.replace(
        "from django.db.models.signals import post_save",
        "from django.db.models.signals import post_save\nfrom tenants.models import Tenant\nfrom .utils import seed_default_coa"
    )
    # Add signal at the end
    s += '''

@receiver(post_save, sender=Tenant)
def create_default_coa_for_new_tenant(sender, instance, created, **kwargs):
    """When a new clinic registers, automatically create their Chart of Accounts."""
    if created:
        seed_default_coa(instance)
'''
    sp.write_text(s, encoding="utf-8")
    print("   added Tenant post_save signal")

# ─── 3. Backfill Existing Tenants ──────────────────────────────────────
print("\\n==> Backfilling existing tenants with COA")
backfill_script = """
from tenants.models import Tenant
from accounting.utils import seed_default_coa

for t in Tenant.objects.all():
    seed_default_coa(t)
    print(f"Seeded COA for {t.name}")
"""
r = subprocess.run([str(PY), "manage.py", "shell", "-c", backfill_script], cwd=ROOT, env=ENV, capture_output=True, text=True)
print(r.stdout)
if r.returncode != 0:
    print(r.stderr)
    sys.exit(1)

# ─── 4. Commit and Push ────────────────────────────────────────────────
print("\\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(accounting): auto-seed standard Chart of Accounts for new and existing clinics", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\\n", "\\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\\n", "\\n   "))

print("\\n✅ Pushed!")
print("\\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")