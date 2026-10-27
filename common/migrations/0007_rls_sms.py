from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0005_smsconfig"),
        ("notifications", "0001_initial"),
        ("common", "0006_rls_appointments"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_smsconfig" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_smsconfig" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_smsconfig";
                CREATE POLICY tenant_isolation ON "tenants_smsconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

                ALTER TABLE "notifications_smslog" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "notifications_smslog" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "notifications_smslog";
                CREATE POLICY tenant_isolation ON "notifications_smslog"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "notifications_smslog";
                ALTER TABLE "notifications_smslog" DISABLE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_smsconfig";
                ALTER TABLE "tenants_smsconfig" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
