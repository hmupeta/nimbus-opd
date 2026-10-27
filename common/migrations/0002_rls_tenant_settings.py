from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_tenant_address_line_1_tenant_address_line_2_and_more"),
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
