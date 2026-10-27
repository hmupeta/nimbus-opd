#!/usr/bin/env python3
"""
fix_org_settings.py -- unblock the org-settings migration by reordering.
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


# ─── 1. Delete the orphan RLS migration ────────────────────────────────
broken = ROOT / "common" / "migrations" / "0002_rls_tenant_settings.py"
if broken.exists():
    broken.unlink()
    print(f"   deleted {broken.relative_to(ROOT)}")
else:
    print(f"   {broken.relative_to(ROOT)} already absent")

# ─── 2. Generate the tenants migration ─────────────────────────────────
print("==> makemigrations tenants")
sh(PY, "manage.py", "makemigrations", "tenants")

# ─── 3. Find the newest tenants migration file ─────────────────────────
tenants_migrations = sorted(
    (ROOT / "tenants" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest = tenants_migrations[-1]
latest_name = latest.stem  # e.g. "0002_tenantsettings"
print(f"   newest tenants migration: {latest_name}")

# ─── 4. Write the RLS migration depending on the actual file ───────────
content = f'''\
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "{latest_name}"),
        ("common", "0001_rls_policies"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_tenantsettings" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_tenantsettings" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_tenantsettings";
                CREATE POLICY tenant_isolation ON "tenants_tenantsettings"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_tenantsettings";
                ALTER TABLE "tenants_tenantsettings" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
'''
broken.write_text(content, encoding="utf-8")
print(f"   wrote {broken.relative_to(ROOT)} (depends on tenants.{latest_name})")

# ─── 5. Apply ──────────────────────────────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 6. Reseed so new Tenants get TenantSettings rows ──────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Admin: /admin/tenants/tenant/ now shows org profile + settings.")