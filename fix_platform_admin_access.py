#!/usr/bin/env python3
"""
fix_platform_admin_access.py -- Grant platform admin rights to admin@demo.local and fix UI.
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

# 1. Update the database
print("==> Granting Platform Admin rights to admin@demo.local")
script = """
from tenants.models import User
u = User.objects.filter(email='admin@demo.local').first()
if u:
    u.is_platform_admin = True
    u.save()
    print('   Success: admin@demo.local is now a Platform Admin.')
else:
    print('   Error: admin@demo.local not found.')
"""
subprocess.run([str(PY), "manage.py", "shell", "-c", script], check=True)

# 2. Ensure Layout.tsx has the tab
print("==> Ensuring Layout.tsx has the Platform Admin tab")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Platform Admin" not in l:
    l = l.replace(
        '            {user?.role === "receptionist" || user?.role === "admin" ? (\n              <NavLink to="/billing" className={linkClass}>Billing</NavLink>\n            ) : null}',
        '            {user?.role === "receptionist" || user?.role === "admin" ? (\n              <NavLink to="/billing" className={linkClass}>Billing</NavLink>\n            ) : null}\n\n            {user?.is_platform_admin && (\n              <NavLink to="/platform" className={linkClass}>Platform Admin</NavLink>\n            )}'
    )
    lp.write_text(l, encoding="utf-8")
    print("   patched Layout.tsx")
else:
    print("   Layout.tsx already contains the tab.")

# 3. Ensure auth.ts interface has the field
print("==> Ensuring auth.ts interface has is_platform_admin")
at = FRONTEND / "src" / "api" / "auth.ts"
a = at.read_text(encoding="utf-8")
if "is_platform_admin" not in a:
    a = a.replace(
        "  exp: number;\n}",
        "  exp: number;\n  is_platform_admin: boolean;\n}"
    )
    at.write_text(a, encoding="utf-8")
    print("   patched auth.ts")

print("==> Done. Please Sign Out and Sign In again.")