#!/usr/bin/env python3
"""
fix_invoice_crash.py -- Fix UnboundLocalError in generate_invoice and enforce ordering.
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

# ─── 1. Fix the UnboundLocalError in generate_invoice ──────────────────
# We remove the inline import inside the function.
v = v.replace("        from billing.models import Invoice, InvoiceItem\n        from decimal import Decimal", "        from decimal import Decimal")
v = v.replace("        from billing.models import Invoice, InvoiceItem\n", "")

# Ensure Invoice and InvoiceItem are imported at the top of the file
if "from billing.models import Invoice" not in v:
    v = v.replace(
        "from billing.models import Payment",
        "from billing.models import Invoice, InvoiceItem, Payment"
    )
    # Or if they aren't imported at all, add them to the main import block
    if "from billing.models import Invoice" not in v:
        v = v.replace(
            "from appointments.models import Appointment",
            "from appointments.models import Appointment\nfrom billing.models import Invoice, InvoiceItem, Payment"
        )

print("   fixed UnboundLocalError in generate_invoice")

# ─── 2. Enforce ordering in VisitViewSet ───────────────────────────────
old_visit_qs = '''    def get_queryset(self):
        qs = Visit.objects.all()
        st = self.request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        pid = self.request.query_params.get("patient")
        if pid:
            qs = qs.filter(patient_id=pid)
        return qs'''

new_visit_qs = '''    def get_queryset(self):
        qs = Visit.objects.all().order_by("-id")
        st = self.request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        pid = self.request.query_params.get("patient")
        if pid:
            qs = qs.filter(patient_id=pid)
        return qs'''

if old_visit_qs in v:
    v = v.replace(old_visit_qs, new_visit_qs)
    print("   fixed VisitViewSet ordering")

# ─── 3. Enforce ordering in InvoiceViewSet ─────────────────────────────
old_inv_qs = '''    def get_queryset(self):
        qs = super().get_queryset()
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs'''

new_inv_qs = '''    def get_queryset(self):
        qs = super().get_queryset().order_by("-id")
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs'''

if old_inv_qs in v:
    v = v.replace(old_inv_qs, new_inv_qs)
    print("   fixed InvoiceViewSet ordering")

# ─── 4. Enforce ordering in PharmacyOrderViewSet ───────────────────────
old_pharm_qs = '''    def get_queryset(self):
        qs = super().get_queryset()
        inv = self.request.query_params.get("visit")
        if inv:
            qs = qs.filter(visit_id=inv)
        patient = self.request.query_params.get("patient")
        if patient:
            qs = qs.filter(visit__patient_id=patient)
        return qs'''

new_pharm_qs = '''    def get_queryset(self):
        qs = super().get_queryset().order_by("-id")
        inv = self.request.query_params.get("visit")
        if inv:
            qs = qs.filter(visit_id=inv)
        patient = self.request.query_params.get("patient")
        if patient:
            qs = qs.filter(visit__patient_id=patient)
        return qs'''

if old_pharm_qs in v:
    v = v.replace(old_pharm_qs, new_pharm_qs)
    print("   fixed PharmacyOrderViewSet ordering")


vp.write_text(v, encoding="utf-8")

# ─── 5. Check ──────────────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Done. You MUST restart the Django server.")