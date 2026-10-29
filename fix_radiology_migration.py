#!/usr/bin/env python3
"""
fix_radiology_migration.py -- Delete broken RLS migration, generate the
radiology migration, then rewrite RLS with correct dependency.
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

def sh(*cmd, capture=False):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run(
        [str(c) for c in cmd], check=True, env=ENV,
        capture_output=capture, text=capture,
    )

# ─── 1. Delete the broken RLS migration ────────────────────────────────
broken_rls = ROOT / "common" / "migrations" / "0008_rls_rad_exam.py"
if broken_rls.exists():
    broken_rls.unlink()
    print(f"   deleted {broken_rls.name}")
else:
    print(f"   {broken_rls.name} already absent")

# ─── 2. Run makemigrations radiology (should succeed now) ──────────────
print("\n==> makemigrations radiology")
r = sh(PY, "manage.py", "makemigrations", "radiology", capture=True)
print("   " + (r.stdout or "(no output)").strip().replace("\n", "\n   "))

# ─── 3. Find the newly generated radiology migration ───────────────────
rad_migrations = sorted(
    (ROOT / "radiology" / "migrations").glob("000[4-9]*.py"),
    key=lambda p: p.name,
)
if not rad_migrations:
    sys.exit("   ❌ No new radiology migration was generated!")
latest_rad = rad_migrations[-1]
latest_rad_name = latest_rad.stem
print(f"   newest radiology migration: {latest_rad_name}")

# ─── 4. Recreate the RLS migration with the correct dependency ─────────
print("\n==> Writing corrected RLS migration")
rls_content = f'''from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("radiology", "{latest_rad_name}"),
        ("common", "0007_rls_sms"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "radiology_radiologyexam" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "radiology_radiologyexam" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "radiology_radiologyexam";
                CREATE POLICY tenant_isolation ON "radiology_radiologyexam"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "radiology_radiologyexam";
                ALTER TABLE "radiology_radiologyexam" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
'''
broken_rls.write_text(rls_content, encoding="utf-8")
print(f"   wrote {broken_rls.name} (depends on radiology.{latest_rad_name})")

# ─── 5. Run migrate ────────────────────────────────────────────────────
print("\n==> migrate")
r = sh(PY, "manage.py", "migrate", capture=True)
for line in (r.stdout or "").splitlines():
    if "Applying" in line or "Running migrations" in line or "No migrations" in line:
        print("   " + line)

# ─── 6. Final check ────────────────────────────────────────────────────
print("\n==> manage.py check")
r = sh(PY, "manage.py", "check", capture=True)
print("   " + (r.stdout.strip().splitlines()[-1] if r.stdout else "OK"))

print("\n✅ All done. Push and redeploy both services.")