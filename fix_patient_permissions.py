#!/usr/bin/env python3
"""
fix_patient_permissions.py -- Explicitly allow Pharmacists and Lab Techs to view patients.
"""
from __future__ import annotations

import os
import re
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

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Find the PatientViewSet and replace its permission_classes
# We use regex to match from "class PatientViewSet" up to the next "def" or "class"
pattern = re.compile(r"(class PatientViewSet\(TenantScopedViewSet\):.*?permission_classes\s*=\s*\[require_roles\((.*?)\)\])", re.DOTALL)

def replacer(match):
    # Replace whatever roles are there with the full list
    return match.group(1).replace(match.group(2), '"admin", "receptionist", "doctor", "nurse", "pharmacist", "lab"')

new_v, count = pattern.subn(replacer, v, count=1)

if count == 1:
    vp.write_text(new_v, encoding="utf-8")
    print("   patched PatientViewSet permissions in api/views.py")
else:
    print("   [WARN] Could not find PatientViewSet permission block automatically.")
    # Fallback: just do a blind replace of the known roles string
    v = v.replace(
        'permission_classes = [require_roles(\n        "admin", "receptionist", "doctor", "nurse")]',
        'permission_classes = [require_roles(\n        "admin", "receptionist", "doctor", "nurse", "pharmacist", "lab")]'
    )
    vp.write_text(v, encoding="utf-8")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. You MUST restart the Django server for the permission changes to take effect.")