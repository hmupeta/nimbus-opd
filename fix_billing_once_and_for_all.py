#!/usr/bin/env python3
"""
fix_billing_once_and_for_all.py -- Guarantee InvoiceViewSet returns data and fix generation.
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

FRONTEND = ROOT / "frontend"
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# 1. Overwrite the entire InvoiceViewSet to use pure all_objects (RLS handles security)
pattern = re.compile(r"class InvoiceViewSet\(viewsets\.ModelViewSet\):.*?(?=\nclass |\Z)", re.DOTALL)

new_invoice_view = '''class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        # Rely on PostgreSQL RLS for tenant isolation
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

# 2. Fix generate_invoice to ensure it returns a clear 200 with the invoice
old_gen = '''        if Invoice.all_objects.filter(visit=visit).exists():
            inv = Invoice.all_objects.get(visit=visit)
            return Response({"detail": "Invoice already exists", "invoice_id": inv.id})'''
new_gen = '''        if Invoice.all_objects.filter(visit=visit).exists():
            inv = Invoice.all_objects.get(visit=visit)
            return Response(InvoiceSerializer(inv).data)'''
if old_gen in v:
    v = v.replace(old_gen, new_gen)
    vp.write_text(v, encoding="utf-8")
    print("   patched generate_invoice to return full data.")

# 3. Fix frontend to handle the direct response
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

old_mut = '''  const generateInvoice = useMutation({
    mutationFn: async (visitId: number) => {
      const { data } = await api.post(`/visits/${visitId}/generate_invoice/`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoice"] }),
  });'''

new_mut = '''  const generateInvoice = useMutation({
    mutationFn: async (visitId: number) => {
      const { data } = await api.post(`/visits/${visitId}/generate_invoice/`);
      return data;
    },
    onSuccess: (data: any) => {
      // If the backend returned the invoice directly, set it in the cache instantly
      if (data && data.id) {
        qc.setQueryData(["invoice", selectedVisit], data);
      }
      qc.invalidateQueries({ queryKey: ["invoice"] });
    },
  });'''

if old_mut in b:
    b = b.replace(old_mut, new_mut)
    bp.write_text(b, encoding="utf-8")
    print("   patched BillingDashboard.tsx to inject invoice directly into cache.")

print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done. Restart the Django server.")