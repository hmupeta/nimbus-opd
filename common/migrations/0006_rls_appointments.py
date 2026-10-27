from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0001_initial"),
        ("visits", "0001_initial"),
        ("common", "0005_rls_gateways"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "appointments_appointment" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "appointments_appointment" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "appointments_appointment";
                CREATE POLICY tenant_isolation ON "appointments_appointment"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "appointments_appointment";
                ALTER TABLE "appointments_appointment" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
