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
