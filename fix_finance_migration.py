#!/usr/bin/env python3
"""
fix_finance_migration.py
  - Deletes the broken RLS migration for finance.
  - Runs makemigrations with full error output shown.
  - Rewrites the RLS migration with the ACTUAL generated migration name.
  - Runs migrate.
"""
from __future__ import annotations
import os
import re
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

def run(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=False, cwd=ROOT, env=ENV,
                          capture_output=True, text=True)

# ─── 1. Delete the broken RLS migration ────────────────────────────────
broken_rls = ROOT / "common" / "migrations" / "0009_rls_finance.py"
if broken_rls.exists():
    broken_rls.unlink()
    print(f"   deleted {broken_rls.name}")
else:
    print(f"   {broken_rls.name} already absent")

# ─── 2. Run makemigrations WITH visible output ─────────────────────────
print("\n==> makemigrations accounting (with full output)")
r = run(PY, "manage.py", "makemigrations", "accounting")
print("   STDOUT:")
for line in (r.stdout or "").splitlines():
    print(f"     {line}")
if r.stderr.strip():
    print("   STDERR:")
    for line in r.stderr.splitlines():
        print(f"     {line}")

if r.returncode != 0:
    print("\n❌ makemigrations failed. This usually means the model file has an error.")
    print("   Common causes:")
    print("   - A field removed from models.py but the DB has data depending on it")
    print("   - An existing migration that conflicts")
    print("   - A circular import")
    print("\n   The full error above will tell us exactly what to fix.")
    sys.exit(1)

# ─── 3. Find the newest accounting migration ───────────────────────────
print("\n==> Finding newest accounting migration")
acc_migrations = sorted(
    (ROOT / "accounting" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
if not acc_migrations:
    sys.exit("   ❌ No accounting migrations found at all!")

latest_acc = acc_migrations[-1]
latest_acc_name = latest_acc.stem
print(f"   newest accounting migration: {latest_acc_name}")

# ─── 4. Rewrite the RLS migration with the correct dependency ──────────
print("\n==> Writing corrected RLS migration")
rls_content = f'''from django.db import migrations


TENANT_TABLES = [
    "accounting_supplier",
    "accounting_bill",
    "accounting_expense",
    "accounting_fixedasset",
]


def enable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{{tbl}}" ENABLE ROW LEVEL SECURITY;')
            cur.execute(f'ALTER TABLE "{{tbl}}" FORCE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{{tbl}}";')
            cur.execute(f"""
                CREATE POLICY tenant_isolation ON "{{tbl}}"
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """)


def disable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{{tbl}}" DISABLE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{{tbl}}";')


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "{latest_acc_name}"),
        ("common", "0008_rls_rad_exam"),
    ]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
'''
broken_rls.write_text(rls_content, encoding="utf-8")
print(f"   wrote {broken_rls.name} (depends on accounting.{latest_acc_name})")

# ─── 5. Run migrate ────────────────────────────────────────────────────
print("\n==> migrate")
r = run(PY, "manage.py", "migrate")
for line in (r.stdout or "").splitlines():
    if "Applying" in line or "Running migrations" in line or "No migrations" in line or "OK" in line:
        print("   " + line)
if r.returncode != 0:
    print("   ❌ migrate failed:")
    for line in (r.stderr or r.stdout).splitlines()[-20:]:
        print("     " + line)
    sys.exit(1)

# ─── 6. Final check ────────────────────────────────────────────────────
print("\n==> manage.py check")
r = run(PY, "manage.py", "check")
print("   " + (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "no output"))
if r.returncode != 0:
    for line in (r.stderr or r.stdout).splitlines()[-20:]:
        print("     " + line)
    sys.exit(1)

# ─── 7. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT, env=ENV)

sh("git", "add", ".")
sh("git", "commit", "-m", "fix(accounting): correct RLS migration dependency and add finance models")
sh("git", "push", "origin", "main")

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")