#!/usr/bin/env python3
"""
fix_invoice_serializer_import.py -- Add InvoiceSerializer to views.py imports.
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

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_imports = '''from .serializers import (
    ClinicalNoteSerializer, LabOrderSerializer, LabResultSerializer,'''
new_imports = '''from .serializers import (
    InvoiceSerializer,
    ClinicalNoteSerializer, LabOrderSerializer, LabResultSerializer,'''

if "InvoiceSerializer," not in v:
    v = v.replace(old_imports, new_imports)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py (added InvoiceSerializer)")
else:
    print("   api/views.py already imports InvoiceSerializer.")

print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)
print("==> Done. Restart your Django server.")