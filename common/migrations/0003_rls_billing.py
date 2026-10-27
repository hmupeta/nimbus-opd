from django.db import migrations


TENANT_TABLES = [
    "billing_insuranceprovider",
    "billing_patientinsurance",
    "billing_invoice",
    "billing_invoiceitem",
    "billing_payment",
    "billing_insuranceclaim",
]

POLICY_SQL = """
    ALTER TABLE "{tbl}" ENABLE ROW LEVEL SECURITY;
    ALTER TABLE "{tbl}" FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";
    CREATE POLICY tenant_isolation ON "{tbl}"
        USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""


def enable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(POLICY_SQL.format(tbl=tbl))


def disable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{tbl}" DISABLE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";')


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
        ("common", "0002_rls_tenant_settings"),
    ]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
