#!/usr/bin/env python3
"""
fix_appointments.py -- remove the duplicate FK, fix the check-in view,
                       and run migrations.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


# ─── 1. Remove the duplicate field from visits/models.py ───────────────
vp = ROOT / "visits" / "models.py"
v = vp.read_text(encoding="utf-8")

old_field = (
    "    appointment = models.OneToOneField('appointments.Appointment', "
    "on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_visit')\n"
)

if old_field in v:
    v = v.replace(old_field, "")
    vp.write_text(v, encoding="utf-8")
    print("   removed duplicate 'appointment' field from visits/models.py")
else:
    print("   [info] duplicate 'appointment' field already absent")

# ─── 2. Fix appointment_views.py check-in logic ────────────────────────
avp = ROOT / "api" / "appointment_views.py"
av = avp.read_text(encoding="utf-8")

old_visit = '''        visit = Visit.objects.create(
            patient=appt.patient,
            attending_doctor=appt.doctor,
            visit_type=Visit.Type.OPD,
            status=Visit.Status.OPEN,
            appointment=appt
        )'''

new_visit = '''        visit = Visit.objects.create(
            patient=appt.patient,
            attending_doctor=appt.doctor,
            visit_type=Visit.Type.OPD,
            status=Visit.Status.OPEN,
        )'''

if old_visit in av:
    av = av.replace(old_visit, new_visit)
    avp.write_text(av, encoding="utf-8")
    print("   fixed appointment_views.py (removed appointment=appt)")
else:
    print("   [info] check-in logic already fixed or not found")

# ─── 3. Run makemigrations cleanly ─────────────────────────────────────
print("==> makemigrations appointments visits")
sh(PY, "manage.py", "makemigrations", "appointments", "visits")

# ─── 4. Find the newest visits migration for the RLS dependency ────────
visits_migrations = sorted(
    (ROOT / "visits" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest_visits = visits_migrations[-1].stem
print(f"   newest visits migration: {latest_visits}")

appointments_migrations = sorted(
    (ROOT / "appointments" / "migrations").glob("0*.py"),
    key=lambda p: p.name,
)
latest_appts = appointments_migrations[-1].stem
print(f"   newest appointments migration: {latest_appts}")

# ─── 5. Rewrite the RLS migration with correct dependencies ────────────
rls_path = ROOT / "common" / "migrations" / "0006_rls_appointments.py"
rls_path.write_text(f'''\
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "{latest_appts}"),
        ("visits", "{latest_visits}"),
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
''', encoding="utf-8")
print(f"   rewrote common/migrations/0006_rls_appointments.py")

# ─── 6. Migrate ────────────────────────────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 7. Check ──────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. You can now schedule appointments and check patients in.")