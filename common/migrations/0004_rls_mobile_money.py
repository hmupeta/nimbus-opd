from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0003_tenantsettings_enable_mobile_money_mobilemoneyconfig"),
        ("common", "0003_rls_billing"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_mobilemoneyconfig"
                    ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_mobilemoneyconfig"
                    FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation
                    ON "tenants_mobilemoneyconfig";
                CREATE POLICY tenant_isolation ON "tenants_mobilemoneyconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation
                    ON "tenants_mobilemoneyconfig";
                ALTER TABLE "tenants_mobilemoneyconfig"
                    DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
