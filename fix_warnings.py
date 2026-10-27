#!/usr/bin/env python3
"""
fix_warnings.py -- Fix SECRET_KEY length and add default ordering to models.
"""
from __future__ import annotations

import os
import secrets
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


def patch_model_ordering(path: Path, model_name: str):
    """Add ordering to the Meta class of a model if it doesn't exist."""
    if not path.exists():
        return
    
    content = path.read_text(encoding="utf-8")
    if f"class {model_name}" not in content:
        return
        
    # Check if ordering is already there
    # We look for the Meta class inside the model
    import re
    # Find the Meta class block
    pattern = re.compile(r"(class " + model_name + r".*?class Meta:)(.*?)(?=\n    def |\nclass |\Z)", re.DOTALL)
    match = pattern.search(content)
    
    if match:
        meta_body = match.group(2)
        if "ordering" not in meta_body:
            # Add ordering to existing Meta
            new_meta = match.group(1) + meta_body + "\n        ordering = ['-id']"
            content = content.replace(match.group(0), new_meta)
            path.write_text(content, encoding="utf-8")
            print(f"   added ordering to {model_name} in {path.name}")
    else:
        # If no Meta class exists, we'd have to create one. 
        # For simplicity, we'll skip models without Meta to avoid breaking files.
        pass


# ─── 1. Fix SECRET_KEY ─────────────────────────────────────────────────
print("==> Generating secure SECRET_KEY")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

if 'SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")' in s:
    new_key = secrets.token_urlsafe(50)
    s = s.replace(
        'SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")',
        f'SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "{new_key}")'
    )
    sp.write_text(s, encoding="utf-8")
    print("   generated new 50-byte SECRET_KEY")

# ─── 2. Add ordering to Models ─────────────────────────────────────────
print("==> Adding default ordering to models")
models_to_patch = [
    ("radiology/models.py", "RadiologyOrder"),
    ("lab/models.py", "LabOrder"),
    ("lab/models.py", "LabTest"),
    ("pharmacy/models.py", "Medicine"),
    ("visits/models.py", "Visit"),
    ("patients/models.py", "Patient"),
    ("billing/models.py", "Invoice"),
]

for file_path, model_name in models_to_patch:
    patch_model_ordering(ROOT / file_path, model_name)

# ─── 3. Run Migrations ─────────────────────────────────────────────────
print("==> makemigrations")
sh(PY, "manage.py", "makemigrations")

print("==> migrate")
sh(PY, "manage.py", "migrate")

print("==> Done. Restart your Django server.")