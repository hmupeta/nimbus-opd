#!/usr/bin/env python3
"""
fix_invoice_queryset.py -- Force InvoiceViewSet to use dynamic get_queryset and clear sessions.
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

# Replace InvoiceViewSet's class-level queryset with a dynamic get_queryset
old_inv_view = '''class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        qs = super().get_queryset().order_by("-id")'''

new_inv_view = '''class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        # Evaluate at request time to respect the tenant context
        qs = Invoice.objects.all().order_by("-id")'''

if old_inv_view in v:
    v = v.replace(old_inv_view, new_inv_view)
    vp.write_text(v, encoding="utf-8")
    print("   patched InvoiceViewSet queryset")
else:
    print("   [WARN] Could not find exact InvoiceViewSet block. Attempting regex...")
    pattern = re.compile(r"(class InvoiceViewSet.*?def get_queryset\(self\):\n\s*qs = ).*?(\.order_by\(\"-id\"\))", re.DOTALL)
    v = pattern.sub(r"\1Invoice.objects.all()\2", v)
    vp.write_text(v, encoding="utf-8")
    print("   patched via regex")

# 2. Clear Django sessions to fix "Session data corrupted"
print("==> Clearing old Django sessions")
sh(PY, "manage.py", "clearsessions")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Done. Restart your Django server.")