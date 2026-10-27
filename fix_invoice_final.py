#!/usr/bin/env python3
"""
fix_invoice_final.py -- Force InvoiceViewSet to fetch fresh data per request.
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

# We will overwrite the entire InvoiceViewSet class to be absolutely sure.
pattern = re.compile(r"class InvoiceViewSet\(viewsets\.ModelViewSet\):.*?(?=\nclass |\Z)", re.DOTALL)

new_invoice_view = '''class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        # Use all_objects to bypass TenantManager cache, rely on Postgres RLS
        qs = Invoice.all_objects.all().order_by("-id")
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        inv = self.get_object()
        if inv.status != Invoice.Status.DRAFT:
            return Response({"detail": "Only drafts can be issued"},
                            status=status.HTTP_409_CONFLICT)
        inv.issued_at = timezone.now()
        inv.status = Invoice.Status.ISSUED
        inv.save(update_fields=["issued_at", "status"])
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        inv = self.get_object()
        inv.recalculate()
        return Response(InvoiceSerializer(inv).data)
'''

if pattern.search(v):
    v = pattern.sub(new_invoice_view, v)
    vp.write_text(v, encoding="utf-8")
    print("   replaced InvoiceViewSet entirely.")
else:
    print("   [WARN] Could not find InvoiceViewSet.")

print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done. Restart your Django server.")