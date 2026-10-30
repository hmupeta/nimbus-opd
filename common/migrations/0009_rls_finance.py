from django.db import migrations


TENANT_TABLES = [
    "accounting_supplier",
    "accounting_bill",
    "accounting_expense",
    "accounting_fixedasset",
]


def enable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{tbl}" ENABLE ROW LEVEL SECURITY;')
            cur.execute(f'ALTER TABLE "{tbl}" FORCE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";')
            cur.execute(f"""
                CREATE POLICY tenant_isolation ON "{tbl}"
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """)


def disable_rls(apps, schema_editor):
    with schema_editor.connection.cursor() as cur:
        for tbl in TENANT_TABLES:
            cur.execute(f'ALTER TABLE "{tbl}" DISABLE ROW LEVEL SECURITY;')
            cur.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{tbl}";')


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0003_alter_journalentry_reference_expense_fixedasset_and_more"),
        ("common", "0008_rls_rad_exam"),
    ]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
