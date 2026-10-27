#!/usr/bin/env python3
"""
add_pharmacy_patient_history.py -- Allow pharmacists to view patients and see their dispensing history.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
if not FRONTEND.exists():
    sys.exit(f"Frontend not found at {FRONTEND}.")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")


# ─── 1. BACKEND: Fix Permissions & Add Patient Filter ──────────────────
print("==> Patching api/views.py")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# 1a. Allow Pharmacists & Lab techs to view Patients
v = v.replace(
    'permission_classes = [require_roles(\n        "admin", "receptionist", "doctor", "nurse")]\n\n    def get_queryset(self):\n        qs = Patient.objects.all()',
    'permission_classes = [require_roles(\n        "admin", "receptionist", "doctor", "nurse", "pharmacist", "lab")]\n\n    def get_queryset(self):\n        qs = Patient.objects.all()'
)

# 1b. Add patient filter to PharmacyOrderViewSet
old_pharm_qs = '''    def get_queryset(self):
        qs = super().get_queryset()
        inv = self.request.query_params.get("visit")
        if inv:
            qs = qs.filter(visit_id=inv)
        return qs'''

new_pharm_qs = '''    def get_queryset(self):
        qs = super().get_queryset()
        inv = self.request.query_params.get("visit")
        if inv:
            qs = qs.filter(visit_id=inv)
        patient = self.request.query_params.get("patient")
        if patient:
            qs = qs.filter(visit__patient_id=patient)
        return qs'''

if old_pharm_qs in v:
    v = v.replace(old_pharm_qs, new_pharm_qs)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")
else:
    print("   [WARN] Could not patch PharmacyOrderViewSet queryset.")

# ─── 2. FRONTEND: Update PatientDetail to show Dispensing History ──────
print("==> Updating PatientDetail.tsx")
pdp = FRONTEND / "src" / "pages" / "PatientDetail.tsx"
pd = pdp.read_text(encoding="utf-8")

# 2a. Add import for Paginated
if "Paginated" not in pd:
    pd = pd.replace(
        'import type { Patient } from "../api/types";',
        'import type { Patient, Paginated } from "../api/types";'
    )

# 2b. Add query for pharmacy orders
if "const pharmOrders =" not in pd:
    pd = pd.replace(
        '  const { data: p, isLoading } = useQuery({',
        '''  const pharmOrders = useQuery({
    queryKey: ["patient", id, "pharmacy"],
    queryFn: async () => (await api.get<Paginated<any>>(`/pharmacy-orders/?patient=${id}`)).data.results,
    enabled: !!id,
  });

  const { data: p, isLoading } = useQuery({'''
    )

# 2c. Add the "Dispensing History" Card just before the Clinical Snapshot
old_clinical = '''        <Card title="Clinical Snapshot" className="md:col-span-2">'''
new_clinical = '''        <Card title="Dispensing History" className="md:col-span-2">
          {!pharmOrders.data || pharmOrders.data.length === 0 ? (
            <p className="text-sm text-slate-500">No medications dispensed for this patient.</p>
          ) : (
            <ul className="divide-y text-sm">
              {pharmOrders.data.map((o: any) => (
                <li key={o.id} className="py-3">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-medium text-slate-700">{o.visit_no}</span>
                    <span className="text-xs text-slate-500">
                      {o.dispensed_at ? new Date(o.dispensed_at).toLocaleDateString() : "Pending"}
                    </span>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {o.items.map((i: any) => (
                      <span key={i.id} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">
                        {i.quantity_dispensed}x {i.medicine_name}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Clinical Snapshot" className="md:col-span-2">'''

if old_clinical in pd:
    pd = pd.replace(old_clinical, new_clinical)
    pdp.write_text(pd, encoding="utf-8")
    print("   patched PatientDetail.tsx")

# ─── 3. Ensure Layout allows Pharmacists to see Patients tab ───────────
print("==> Updating Layout.tsx")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")

# Just to be safe, ensure the Patients link renders for everyone except maybe lab
if '<NavLink to="/patients" className={linkClass}>Patients</NavLink>' not in l:
    # In case the previous patches nested it inside a role check, let's bring it back out
    l = l.replace(
        '{user?.role !== "lab" && (',
        '{true && ('
    )
    lp.write_text(l, encoding="utf-8")

print("==> Done. Restart the Django server and refresh your browser.")