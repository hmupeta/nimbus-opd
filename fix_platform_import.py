#!/usr/bin/env python3
"""
fix_platform_import.py -- Remove the bad import from platform_views.py.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

pv = ROOT / "api" / "platform_views.py"
v = pv.read_text(encoding="utf-8")

# Remove the bad import
v = v.replace("from api.auth import TenantTokenObtainPairSerializer\n", "")
pv.write_text(v, encoding="utf-8")
print("   removed bad import from platform_views.py")

# Verify
print("==> manage.py check")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done. Restart your Django server.")