#!/usr/bin/env python3
"""
fix_invoice_all_objects.py -- Fix InvoiceViewSet to rely on RLS instead of TenantManager.
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

# Replace Invoice.objects with Invoice.all_objects in the ViewSet
old_qs = '''            def get_queryset(self):
                # Evaluate at request time to respect the tenant context
                qs = Invoice.objects.all().order_by("-id")'''
new_qs = '''            def get_queryset(self):
                # Use all_objects to bypass TenantManager and rely on PostgreSQL RLS
                qs = Invoice.all_objects.all().order_by("-id")'''

if old_qs in v:
    v = v.replace(old_qs, new_qs)
    vp.write_text(v, encoding="utf-8")
    print("   patched InvoiceViewSet to use all_objects")
else:
    print("   [WARN] Could not find InvoiceViewSet block. It may already be patched.")

print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done.")