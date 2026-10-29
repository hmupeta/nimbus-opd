from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("radiology", "0004_radiologyexam"),
        ("common", "0007_rls_sms"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "radiology_radiologyexam" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "radiology_radiologyexam" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "radiology_radiologyexam";
                CREATE POLICY tenant_isolation ON "radiology_radiologyexam"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "radiology_radiologyexam";
                ALTER TABLE "radiology_radiologyexam" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
