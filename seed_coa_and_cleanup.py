#!/usr/bin/env python3
"""
seed_coa_and_cleanup.py
  - Creates a management command to seed Chart of Accounts.
  - Updates render.yaml to run it on boot.
  - Deletes empty journal entries from the database.
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

# ─── 1. Create the COA seeding command ─────────────────────────────────
print("==> Creating accounting/management/commands/seed_coa.py")
write("accounting/management/__init__.py", "")
write("accounting/management/commands/__init__.py", "")

write("accounting/management/commands/seed_coa.py", '''\
from django.core.management.base import BaseCommand
from tenants.models import Tenant
from accounting.models import ChartOfAccount
from common.context import db_tenant_context

STANDARD_ACCOUNTS = [
    ("1000", "Cash & Bank", "asset"),
    ("1100", "Accounts Receivable", "asset"),
    ("1200", "Inventory", "asset"),
    ("1500", "Fixed Assets", "asset"),
    ("2000", "Accounts Payable", "liability"),
    ("3000", "Owner's Equity", "equity"),
    ("4000", "Consultation Revenue", "revenue"),
    ("4100", "Pharmacy Revenue", "revenue"),
    ("4200", "Lab Revenue", "revenue"),
    ("4300", "Radiology Revenue", "revenue"),
    ("5000", "Salaries & Wages", "expense"),
    ("5100", "Rent Expense", "expense"),
    ("5200", "Utilities Expense", "expense"),
    ("5300", "Medical Supplies", "expense"),
]

class Command(BaseCommand):
    help = "Seed Standard Chart of Accounts for all tenants."

    def handle(self, *args, **opts):
        total_created = 0
        
        for tenant in Tenant.objects.all():
            with db_tenant_context(tenant):
                created_count = 0
                for code, name, type in STANDARD_ACCOUNTS:
                    obj, created = ChartOfAccount.all_objects.get_or_create(
                        tenant=tenant, code=code,
                        defaults={"name": name, "type": type}
                    )
                    if created:
                        created_count += 1
                
                if created_count > 0:
                    self.stdout.write(f"[COA] {tenant.name}: created {created_count} accounts.")
                    total_created += created_count
                else:
                    self.stdout.write(f"[COA] {tenant.name}: already seeded.")
                    
        self.stdout.write(self.style.SUCCESS(f"seed_coa: {total_created} accounts created."))
''')

# ─── 2. Run it locally to fix your local DB ────────────────────────────
print("\n==> Running seed_coa locally")
sh(PY, "manage.py", "seed_coa")

# ─── 3. Cleanup the broken empty Journal Entries locally ───────────────
print("\n==> Cleaning up empty Journal Entries locally")
cleanup_script = '''
from accounting.models import JournalEntry
from common.context import db_tenant_context
from tenants.models import Tenant

for t in Tenant.objects.all():
    with db_tenant_context(t):
        # Delete JEs that have no lines (the broken ones)
        empty_jes = JournalEntry.all_objects.filter(tenant=t, lines__isnull=True)
        count = empty_jes.count()
        empty_jes.delete()
        if count > 0:
            print(f"Deleted {count} empty Journal Entries for {t.name}")
'''
sh(PY, "manage.py", "shell", "-c", cleanup_script)

# ─── 4. Update render.yaml to run seed_coa on boot ─────────────────────
print("\n==> Updating render.yaml startup command")
ry = ROOT / "render.yaml"
if ry.exists():
    y = ry.read_text(encoding="utf-8")
    old_cmd = "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
    new_cmd = "python manage.py migrate --noinput && python manage.py seed_coa && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
    
    if old_cmd in y:
        y = y.replace(old_cmd, new_cmd)
        ry.write_text(y, encoding="utf-8")
        print("   patched render.yaml (added seed_coa)")
    elif new_cmd in y:
        print("   render.yaml already has seed_coa")
    else:
        print("   [WARN] Could not find exact startCommand string. Please check render.yaml manually.")

# ─── 5. Push ───────────────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "feat(accounting): seed default COA and cleanup empty journal entries", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")