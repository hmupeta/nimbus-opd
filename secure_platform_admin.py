#!/usr/bin/env python3
"""
secure_platform_admin.py -- Isolate Platform Admin from Clinical Data.
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
FRONTEND = ROOT / "frontend"

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)

# ─── 1. Create the untethered Platform Admin ───────────────────────────
print("==> Creating dedicated Platform Admin (tenant=None)")
script = """
from tenants.models import User
from django.contrib.auth.hashers import make_password

# 1. Create the superadmin
if not User.objects.filter(email='superadmin@nimbus.local').exists():
    User.objects.create(
        email='superadmin@nimbus.local',
        password=make_password('demo'),
        first_name='Super',
        last_name='Admin',
        role='admin',
        is_staff=True,
        is_superuser=True,
        is_platform_admin=True,
        tenant=None
    )
    print('   Created superadmin@nimbus.local')
else:
    print('   superadmin@nimbus.local already exists')

# 2. Revoke platform admin from demo's admin to enforce separation
u = User.objects.filter(email='admin@demo.local').first()
if u:
    u.is_platform_admin = False
    u.save()
    print('   Revoked platform admin from admin@demo.local (now a strict Clinic Admin)')
"""
sh(PY, "manage.py", "shell", "-c", script)

# ─── 2. Lock down Django Admin for untethered users ────────────────────
print("==> Updating common/admin.py to block clinical data")
ap = ROOT / "common" / "admin.py"
a = ap.read_text(encoding="utf-8")
if "return qs.none() # Platform admins without a tenant see no clinical data" not in a:
    a = a.replace(
        '''        if getattr(request.user, "is_platform_admin", False):
            return qs''',
        '''        if getattr(request.user, "is_platform_admin", False):
            # Platform admins without a tenant see no clinical data
            if not request.user.tenant:
                return qs.none()
            return qs'''
    )
    ap.write_text(a, encoding="utf-8")
    print("   patched common/admin.py")

# ─── 3. Frontend: Redirect Platform Admin to /platform by default ──────
print("==> Updating Dashboard.tsx to route Platform Admins")
dp = FRONTEND / "src" / "pages" / "Dashboard.tsx"
d = dp.read_text(encoding="utf-8")

if 'if (user?.is_platform_admin) return <Navigate to="/platform" replace />;' not in d:
    d = d.replace(
        'if (user?.role === "lab") return <LabTechDashboard />;',
        'if (user?.is_platform_admin) return <Navigate to="/platform" replace />;\n  if (user?.role === "lab") return <LabTechDashboard />;'
    )
    dp.write_text(d, encoding="utf-8")
    print("   patched Dashboard.tsx")

# ─── 4. Frontend: Hide Clinical Tabs for Platform Admin in Layout ──────
print("==> Updating Layout.tsx to hide clinical tabs for Platform Admin")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")

if 'const isClinicalStaff = !user?.is_platform_admin;' not in l:
    l = l.replace(
        'const linkClass = ({ isActive }: { isActive: boolean }) =>',
        'const isClinicalStaff = !user?.is_platform_admin;\n\n  const linkClass = ({ isActive }: { isActive: boolean }) =>'
    )
    # Wrap the clinical tabs in a conditional
    l = l.replace(
        '<NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>\n            <NavLink to="/patients" className={linkClass}>Patients</NavLink>',
        '{isClinicalStaff && <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>}\n            {isClinicalStaff && <NavLink to="/patients" className={linkClass}>Patients</NavLink>}'
    )
    l = l.replace(
        '{user?.role === "receptionist" || user?.role === "admin" ? (\n              <NavLink to="/appointments" className={linkClass}>Appointments</NavLink>\n            ) : null}',
        '{isClinicalStaff && (user?.role === "receptionist" || user?.role === "admin") ? (\n              <NavLink to="/appointments" className={linkClass}>Appointments</NavLink>\n            ) : null}'
    )
    l = l.replace(
        '{user?.role === "lab" || user?.role === "admin" ? (\n              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>\n            ) : null}',
        '{isClinicalStaff && (user?.role === "lab" || user?.role === "admin") ? (\n              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>\n            ) : null}'
    )
    l = l.replace(
        '{user?.role === "radiology" || user?.role === "admin" ? (\n              <NavLink to="/radiology" className={linkClass}>Radiology</NavLink>\n            ) : null}',
        '{isClinicalStaff && (user?.role === "radiology" || user?.role === "admin") ? (\n              <NavLink to="/radiology" className={linkClass}>Radiology</NavLink>\n            ) : null}'
    )
    l = l.replace(
        '{user?.role === "pharmacist" || user?.role === "admin" ? (\n              <NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>\n            ) : null}',
        '{isClinicalStaff && (user?.role === "pharmacist" || user?.role === "admin") ? (\n              <NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>\n            ) : null}'
    )
    l = l.replace(
        '{user?.role === "pharmacist" || user?.role === "admin" ? (\n              <NavLink to="/stock" className={linkClass}>Stock</NavLink>\n            ) : null}',
        '{isClinicalStaff && (user?.role === "pharmacist" || user?.role === "admin") ? (\n              <NavLink to="/stock" className={linkClass}>Stock</NavLink>\n            ) : null}'
    )
    l = l.replace(
        '{user?.role === "receptionist" || user?.role === "admin" ? (\n              <NavLink to="/billing" className={linkClass}>Billing</NavLink>\n            ) : null}',
        '{isClinicalStaff && (user?.role === "receptionist" || user?.role === "admin") ? (\n              <NavLink to="/billing" className={linkClass}>Billing</NavLink>\n            ) : null}'
    )
    lp.write_text(l, encoding="utf-8")
    print("   patched Layout.tsx")

print("==> Done. You must log out and log back in.")