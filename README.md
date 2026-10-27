# OPD Multi-Tenant System

## Bootstrap
    export DB_USER=opd_owner DB_PASSWORD=opd_owner
    .venv/bin/python manage.py migrate
    .venv/bin/python manage.py seed_demo

## Run (app role = RLS enforced)
    DB_USER=opd_app DB_PASSWORD=opd_app .venv/bin/python manage.py runserver

Login at http://127.0.0.1:8000/admin/
    admin@demo.local / demo

## Verify RLS

    TID=$(psql -U opd_owner -d opd -tAc "SELECT id FROM tenants_tenant WHERE code='demo';")
    psql -U opd_app -d opd -c "SELECT count(*) FROM patients_patient;"              # 0
    psql -U opd_app -d opd -c "SET app.tenant_id = '${TID}';
                               SELECT count(*) FROM patients_patient;"              # 1
    psql -U opd_app -d opd -c "SET app.tenant_id = '00000000-0000-0000-0000-000000000000';
                               SELECT count(*) FROM patients_patient;"              # 0
