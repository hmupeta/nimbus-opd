#!/usr/bin/env python3
"""
fix_invoice_import.py -- Ensure Invoice and InvoiceItem are imported at the top of views.py.
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

# 1. Ensure the billing imports are present at the top of the file.
# We will replace the existing billing import block if it exists.
billing_imports = "from billing.models import (\n    InsuranceClaim, InsuranceProvider, Invoice, InvoiceItem,\n    PatientInsurance, Payment,\n)"

# Find the existing billing import statement (single line or multi-line)
pattern = re.compile(r"from billing\.models import .*?(?=\n(?!\s))", re.DOTALL)

if pattern.search(v):
    v = pattern.sub(billing_imports, v, count=1)
else:
    # If no billing import exists, add it after the clinical imports
    v = v.replace(
        "from clinical.models import ClinicalNote, Order, OrderItem",
        "from clinical.models import ClinicalNote, Order, OrderItem\n" + billing_imports
    )

# 2. Clean up any inline imports of Invoice inside generate_invoice
# (just in case they are causing shadowing issues)
v = re.sub(r"\n\s*from billing\.models import Invoice.*?\n", "\n", v)
v = re.sub(r"\n\s*from decimal import Decimal\n", "\n", v)

# 3. Remove the import line we previously added inside generate_invoice
old_func_start = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "receptionist")])
    def generate_invoice(self, request, pk=None):
        visit = self.get_object()
        if Invoice.all_objects.filter(visit=visit).exists():'''

new_func_start = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "receptionist")])
    def generate_invoice(self, request, pk=None):
        visit = self.get_object()
        from decimal import Decimal
        if Invoice.all_objects.filter(visit=visit).exists():'''

v = v.replace(old_func_start, new_func_start)

vp.write_text(v, encoding="utf-8")
print("   patched api/views.py (Invoice imports)")

# 4. Check
print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done. Restart your Django server.")