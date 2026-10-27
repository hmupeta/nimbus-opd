#!/usr/bin/env python3
"""
add_radiology_and_billing_fix.py -- Add Radiology workflow and auto-billing UI fixes.
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


# ─── 1. BACKEND: Add order_radiology action ────────────────────────────
print("==> Patching api/views.py (Adding order_radiology)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "def order_radiology(self, request, pk=None):" not in v:
    rad_action = '''
    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_radiology(self, request, pk=None):
        visit = self.get_object()
        modality = request.data.get("modality")
        body_part = request.data.get("body_part")
        notes = request.data.get("notes", "")

        if not modality or not body_part:
            return Response({"detail": "modality and body_part are required"}, status=status.HTTP_400_BAD_REQUEST)

        from radiology.models import RadiologyOrder
        
        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.RADIOLOGY, status=Order.Status.PENDING, notes=notes)
            OrderItem.objects.create(order=order, code=f"{modality}-{body_part}", description=f"{modality} {body_part}", quantity=1)
            RadiologyOrder.objects.create(
                visit=visit, order=order, modality=modality, body_part=body_part, status=RadiologyOrder.Status.PENDING
            )

        return Response({"detail": "Radiology ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)
'''
    v = v.replace("class VitalsViewSet(TenantScopedViewSet):", rad_action + "\nclass VitalsViewSet(TenantScopedViewSet):")
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")

# ─── 2. BACKEND: Update RadiologyOrderSerializer ───────────────────────
print("==> Patching api/serializers.py (RadiologyOrderSerializer)")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

old_rad_ser = '''class RadiologyOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = RadiologyOrder
        fields = ["id", "visit", "order", "modality", "body_part", "status",
                  "ordered_at", "performed_at", "performed_by",
                  "findings", "impression", "radiologist",
                  "report_url", "reported_at"]
        read_only_fields = ["id", "ordered_at", "performed_at", "reported_at"]'''

new_rad_ser = '''class RadiologyOrderSerializer(serializers.ModelSerializer):
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)

    class Meta:
        model = RadiologyOrder
        fields = ["id", "visit", "visit_no", "patient_name", "order", "modality", "body_part", "status",
                  "ordered_at", "performed_at", "performed_by",
                  "findings", "impression", "radiologist",
                  "report_url", "reported_at"]
        read_only_fields = ["id", "ordered_at", "performed_at", "reported_at"]'''

if old_rad_ser in s:
    s = s.replace(old_rad_ser, new_rad_ser)
    sp.write_text(s, encoding="utf-8")
    print("   patched api/serializers.py")

# ─── 3. FRONTEND: Create RadiologyDashboard ────────────────────────────
print("==> Creating RadiologyDashboard component")
write_frontend("src/pages/RadiologyDashboard.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function RadiologyDashboard() {
  const qc = useQueryClient();
  const [activeOrder, setActiveOrder] = useState<any | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["rad-orders", "pending"],
    queryFn: async () => (await api.get<Paginated<any>>("/radiology-orders/?status=pending")).data,
  });

  const submitReport = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: any }) => {
      await api.post(`/radiology-orders/${id}/report/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rad-orders"] });
      setActiveOrder(null);
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!activeOrder) return;
    const fd = new FormData(e.currentTarget);
    submitReport.mutate({
      id: activeOrder.id,
      payload: {
        findings: String(fd.get("findings") || ""),
        impression: String(fd.get("impression") || ""),
      },
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Radiology Queue</h1>
      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Examination</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.results.map((o: any) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{o.patient_name}</p>
                  <p className="text-xs text-slate-400">{o.visit_no}</p>
                </td>
                <td className="px-4 py-3">
                  <span className="font-medium">{o.modality}</span> - {o.body_part}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">{o.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => setActiveOrder(o)} className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700">
                    Enter Report
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.results.length === 0 && <p className="p-6 text-center text-slate-500">No pending radiology orders.</p>}
      </div>

      {activeOrder && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="font-semibold text-lg">Radiology Report</h2>
              <button onClick={() => setActiveOrder(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={onSubmit} className="p-4 space-y-4">
              <div className="bg-slate-50 p-3 rounded text-sm mb-4">
                <p><span className="text-slate-500">Patient:</span> <b>{activeOrder.patient_name}</b></p>
                <p><span className="text-slate-500">Exam:</span> <b>{activeOrder.modality} {activeOrder.body_part}</b></p>
              </div>
              <label className="block text-sm">
                <span className="text-slate-600">Findings</span>
                <textarea name="findings" rows={4} required className="mt-1 w-full border rounded px-3 py-2" placeholder="Describe the radiographic findings..." />
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Impression / Conclusion</span>
                <textarea name="impression" rows={2} required className="mt-1 w-full border rounded px-3 py-2" placeholder="Normal, abnormal, etc." />
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setActiveOrder(null)} className="px-4 py-2 text-sm text-slate-600 border rounded hover:bg-slate-50">Cancel</button>
                <button type="submit" disabled={submitReport.isPending} className="px-4 py-2 text-sm text-white bg-emerald-600 rounded hover:bg-emerald-700">
                  {submitReport.isPending ? "Saving..." : "Save Report"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
''')

# ─── 4. FRONTEND: Update VisitTimeline to allow Radiology Ordering ─────
print("==> Updating VisitTimeline.tsx")
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

# 4a. Add state for radiology form
if "const [showRadForm, setShowRadForm] = useState(false);" not in v:
    v = v.replace(
        'const [showLabForm, setShowLabForm] = useState(false);',
        'const [showLabForm, setShowLabForm] = useState(false);\n  const [showRadForm, setShowRadForm] = useState(false);'
    )

# 4b. Add mutation
if "const orderRadiology = useMutation({" not in v:
    v = v.replace(
        'const prescribe = useMutation({',
        '''const orderRadiology = useMutation({
    mutationFn: async (payload: any) => {
      await api.post(`/visits/${id}/order_radiology/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowRadForm(false);
    },
  });

  const prescribe = useMutation({'''
    )

# 4c. Update the UI buttons
old_btns = '''              {!showLabForm && !showMedForm && (
                <div className="flex gap-2">
                  <button onClick={() => setShowLabForm(true)} className="flex-1 text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 py-1.5 rounded hover:bg-indigo-100 font-medium">+ Lab</button>
                  <button onClick={() => setShowMedForm(true)} className="flex-1 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 py-1.5 rounded hover:bg-emerald-100 font-medium">+ Rx</button>
                </div>
              )}'''

new_btns = '''              {!showLabForm && !showMedForm && !showRadForm && (
                <div className="flex gap-2">
                  <button onClick={() => setShowLabForm(true)} className="flex-1 text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 py-1.5 rounded hover:bg-indigo-100 font-medium">+ Lab</button>
                  <button onClick={() => setShowRadForm(true)} className="flex-1 text-xs bg-orange-50 text-orange-700 border border-orange-200 py-1.5 rounded hover:bg-orange-100 font-medium">+ Rad</button>
                  <button onClick={() => setShowMedForm(true)} className="flex-1 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 py-1.5 rounded hover:bg-emerald-100 font-medium">+ Rx</button>
                </div>
              )}'''

if old_btns in v:
    v = v.replace(old_btns, new_btns)

# 4d. Add the form itself (before showMedForm)
if "{showRadForm && (" not in v:
    rad_form = '''
              {showRadForm && (
                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); orderRadiology.mutate({ modality: fd.get("modality"), body_part: fd.get("body_part"), notes: fd.get("notes") }); }} className="space-y-2 bg-orange-50 p-2 rounded border border-orange-100">
                  <div className="grid grid-cols-2 gap-1">
                    <select name="modality" required className="w-full border rounded px-2 py-1 text-xs">
                      <option value="X-ray">X-ray</option>
                      <option value="CT">CT</option>
                      <option value="MRI">MRI</option>
                      <option value="US">Ultrasound</option>
                    </select>
                    <input name="body_part" placeholder="Body Part (e.g. Chest)" required className="w-full border rounded px-2 py-1 text-xs" />
                  </div>
                  <input name="notes" placeholder="Clinical notes..." className="w-full border rounded px-2 py-1 text-xs" />
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setShowRadForm(false)} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderRadiology.isPending} className="text-[10px] bg-orange-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>
              )}
'''
    # Insert right before showMedForm
    v = v.replace("              {showMedForm && (", rad_form + "\n              {showMedForm && (")

vp.write_text(v, encoding="utf-8")
print("   patched VisitTimeline.tsx")

# ─── 5. FRONTEND: Update Navigation and Routing ────────────────────────
print("==> Updating Navigation and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Radiology" not in l:
    l = l.replace(
        '{user?.role === "lab" || user?.role === "admin" ? (\n              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>\n            ) : null}',
        '''{user?.role === "lab" || user?.role === "admin" ? (
              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>
            ) : null}
            {user?.role === "radiology" || user?.role === "admin" ? (
              <NavLink to="/radiology" className={linkClass}>Radiology</NavLink>
            ) : null}'''
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "RadiologyDashboard" not in a:
    a = a.replace(
        'import PharmacyDashboard from "./pages/PharmacyDashboard";',
        'import PharmacyDashboard from "./pages/PharmacyDashboard";\nimport RadiologyDashboard from "./pages/RadiologyDashboard";'
    )
    a = a.replace(
        '<Route path="/pharmacy" element={<PharmacyDashboard />} />',
        '<Route path="/pharmacy" element={<PharmacyDashboard />} />\n          <Route path="/radiology" element={<RadiologyDashboard />} />'
    )
    ap.write_text(a, encoding="utf-8")

# ─── 6. FRONTEND: Fix Billing Dashboard (Remove manual generation) ─────
print("==> Updating BillingDashboard.tsx")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

# Remove the manual generation button block
old_gen = '''          ) : !invoice.data ? (
            <div className="text-center py-8">
              <p className="text-slate-500 text-sm mb-4">No invoice generated yet.</p>
              <button onClick={() => generateInvoice.mutate(selectedVisit)} disabled={generateInvoice.isPending} className="bg-sky-600 text-white px-4 py-2 rounded text-sm hover:bg-sky-700">
                Generate Invoice
              </button>
            </div>
          ) : ('''
new_gen = '''          ) : !invoice.data ? (
            <div className="text-center py-8">
              <p className="text-slate-500 text-sm mb-4">No invoice generated. Make sure the visit is closed.</p>
              <button onClick={() => generateInvoice.mutate(selectedVisit)} disabled={generateInvoice.isPending} className="bg-slate-200 text-slate-700 px-4 py-2 rounded text-sm hover:bg-slate-300">
                Force Generate
              </button>
            </div>
          ) : ('''
if old_gen in b:
    b = b.replace(old_gen, new_gen)
    bp.write_text(b, encoding="utf-8")
    print("   patched BillingDashboard.tsx")

print("==> Done. Restart the Django server and refresh your browser.")