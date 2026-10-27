#!/usr/bin/env python3
"""
fix_swagger_auth.py -- explicitly configure the JWT security scheme
                       so the Authorize button appears in Swagger.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    import sys
    sys.exit("Run this from inside the opd/ directory")

sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

old_block = '''SPECTACULAR_SETTINGS = {
    "TITLE": "OPD Multi-Tenant API",
    "DESCRIPTION": "Outpatient Department multi-tenant backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}'''

new_block = '''SPECTACULAR_SETTINGS = {
    "TITLE": "OPD Multi-Tenant API",
    "DESCRIPTION": "Outpatient Department multi-tenant backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Apply the JWT auth globally to the schema
    "SECURITY": [{"jwtAuth": []}],
    # Explicitly define the JWT Bearer scheme
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "jwtAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}'''

if old_block in s:
    s = s.replace(old_block, new_block)
    sp.write_text(s, encoding="utf-8")
    print("   patched config/settings.py (added JWT security scheme)")
else:
    print("   [WARN] Could not find the exact SPECTACULAR_SETTINGS block.")
    print("   Please open config/settings.py and update it manually.")

print("==> manage.py check")
import subprocess
import sys
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
subprocess.run([str(PY), "manage.py", "check"], check=True)
print("\n==> Done. Restart the server and refresh /api/docs/")