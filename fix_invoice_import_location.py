#!/usr/bin/env python3
"""
fix_invoice_import_location.py -- Move InvoiceSerializer import to billing_serializers.
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

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# 1. Remove InvoiceSerializer from the wrong import block
v = v.replace("    InvoiceSerializer,\n", "")

# 2. Add it to the correct import block (billing_serializers)
if "from .billing_serializers import (" in v:
    # Check if it's already there to avoid duplicates
    if "InvoiceSerializer" not in v.split("from .billing_serializers import (")[1].split(")")[0]:
        v = v.replace(
            "from .billing_serializers import (",
            "from .billing_serializers import (\n    InvoiceSerializer,"
        )
else:
    # If the block doesn't exist, just add the direct import
    v = v.replace(
        "from .serializers import (",
        "from .billing_serializers import InvoiceSerializer\nfrom .serializers import ("
    )

vp.write_text(v, encoding="utf-8")
print("   fixed InvoiceSerializer import in api/views.py")

print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done. Restart your Django server.")