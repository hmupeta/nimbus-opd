#!/usr/bin/env python3
"""
fix_invoice_visibility_final.py -- Explicit tenant filter for invoices and better cache handling.
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

# ─── 1. BACKEND: Explicitly filter by tenant_id ────────────────────────
print("==> Patching api/views.py (InvoiceViewSet)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Use regex to replace the get_queryset inside InvoiceViewSet
pattern = re.compile(r"(class InvoiceViewSet.*?def get_queryset\(self\):).*?(?=\n    @action|\nclass |\Z)", re.DOTALL)

new_get_queryset = '''\\1
        # Explicitly filter by the logged-in user's tenant
        qs = Invoice.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-id")
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs
'''

if pattern.search(v):
    v = pattern.sub(new_get_queryset, v, count=1)
    vp.write_text(v, encoding="utf-8")
    print("   patched InvoiceViewSet get_queryset")

# ─── 2. FRONTEND: Fix cache handling to prevent flash ──────────────────
print("==> Updating BillingDashboard.tsx")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

old_mut = '''  const generateInvoice = useMutation({
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

new_mut = '''  const generateInvoice = useMutation({
    mutationFn: async (visitId: number) => {
      const { data } = await api.post(`/visits/${visitId}/generate_invoice/`);
      return data;
    },
    onSuccess: (data: any) => {
      // Inject the invoice directly into the React Query cache to render immediately
      if (data && data.id) {
        qc.setQueryData(["invoice", selectedVisit], data);
      }
      // Refresh the list of closed visits (to update any invoice indicators)
      qc.invalidateQueries({ queryKey: ["billing-visits"] });
      // Notice we removed `qc.invalidateQueries({ queryKey: ["invoice"] })` 
      // to prevent the background refetch from overwriting our new data with an empty array.
    },
  });'''

if old_mut in b:
    b = b.replace(old_mut, new_mut)
    bp.write_text(b, encoding="utf-8")
    print("   patched BillingDashboard.tsx mutation")

print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True)

print("==> Done. Restart your Django server.")