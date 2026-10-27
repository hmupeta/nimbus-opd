from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0004_paymentgatewayconfig"),
        ("common", "0004_rls_mobile_money"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "tenants_paymentgatewayconfig" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "tenants_paymentgatewayconfig" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_paymentgatewayconfig";
                CREATE POLICY tenant_isolation ON "tenants_paymentgatewayconfig"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "tenants_paymentgatewayconfig";
                ALTER TABLE "tenants_paymentgatewayconfig" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
