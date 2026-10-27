#!/usr/bin/env python3
"""
fix_migration_graph.py -- repair the InconsistentMigrationHistory by
pinning common.0001_rls_policies to explicit migration names.
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


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Rewrite common/0001_rls_policies.py with explicit deps ─────────
write("common/migrations/0001_rls_policies.py", '''\
from django.db import migrations

TENANT_TABLES = [
    "patients_patient",
    "visits_visit",
    "vitals_vitals",
    "vitals_vitaldefinition",
    "vitals_vitalvalue",
    "clinical_clinicalnote",
    "clinical_order",
    "clinical_orderitem",
    "lab_labtest",
    "lab_laborder",
    "lab_labresult",
    "radiology_radiologyorder",
    "pharmacy_medicine",
    "pharmacy_pharmacyorder",
    "pharmacy_pharmacyitem",
    "pharmacy_stock",
    "pharmacy_stockmovement",
    "audit_auditlog",
    "tenants_tenantsequence",
]

POLICY_SQL = """
    ALTER TABLE "{tbl}" ENABLE ROW LEVEL SECURITY;
    ALTER TABLE "{tbl}" FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";
    CREATE POLICY tenant_isolation ON "{tbl}"
        USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""


def _tenant_col_exists(cur, table):
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = %s
          AND column_name  = 'tenant_id'
        """,
        [table],
    )
    return cur.fetchone() is not None


def enable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            if not _tenant_col_exists(cur, tbl):
                print(f"   [rls] skipping {tbl} (no tenant_id column)")
                continue
            cur.execute(POLICY_SQL.format(tbl=tbl))


def disable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            if not _tenant_col_exists(cur, tbl):
                continue
            cur.execute(f'ALTER TABLE "{tbl}" DISABLE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";')


class Migration(migrations.Migration):
    initial = True

    # IMPORTANT: explicit names, NOT __latest__.
    # These are the migrations that were current when this file first ran.
    # Pinning them makes the graph consistent forever, even as new migrations
    # are added to dependent apps.
    dependencies = [
        ("tenants",   "0001_initial"),
        ("patients",  "0002_initial"),
        ("visits",    "0001_initial"),
        ("vitals",    "0001_initial"),
        ("clinical",  "0002_initial"),
        ("lab",       "0002_initial"),
        ("radiology", "0002_initial"),
        ("pharmacy",  "0002_initial"),
        ("audit",     "0002_initial"),
    ]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
''')

# ─── 2. Apply the pending migrations ───────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 3. Reseed so both tenants get TenantSettings rows ─────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

# ─── 4. Sanity check ───────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Verify:")
print("    python manage.py showmigrations common tenants")