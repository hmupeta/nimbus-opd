#!/usr/bin/env python3
"""
fix_pharmacy_ui.py -- Enhance Pharmacy Queue and add Pharmacy visibility to Doctor's View.
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

# ─── 1. BACKEND: Update serializers ────────────────────────────────────
print("==> Patching api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

# Update PharmacyOrderSerializer to include patient_name
if "patient_name = serializers.CharField(source=\"visit.patient.full_name\", read_only=True)" not in s:
    s = s.replace(
        '''class PharmacyOrderSerializer(serializers.ModelSerializer):
    items = PharmacyItemSerializer(many=True, read_only=True)
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)''',
        '''class PharmacyOrderSerializer(serializers.ModelSerializer):
    items = PharmacyItemSerializer(many=True, read_only=True)
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)'''
    )
    sp.write_text(s, encoding="utf-8")
    print("   patched PharmacyOrderSerializer")

# ─── 2. FRONTEND: Update PharmacyDashboard ─────────────────────────────
print("==> Rewriting src/pages/PharmacyDashboard.tsx")
write_frontend("src/pages/PharmacyDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacyDashboard() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-orders"],
    queryFn: async () => {
      // Fetch both pending and dispensed so we have a full history
      const pending = await api.get<Paginated<any>>("/pharmacy-orders/?status=pending");
      const dispensed = await api.get<Paginated<any>>("/pharmacy-orders/?status=dispensed");
      return [...pending.data.results, ...dispensed.data.results];
    },
  });

  const dispense = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/pharmacy-orders/${id}/dispense/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pharmacy-orders"] }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Pharmacy Queue</h1>
      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Medications (Prescribed → Dispensed)</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((o: any) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{o.patient_name || o.visit_no}</p>
                  <p className="text-xs text-slate-400">{o.visit_no}</p>
                </td>
                <td className="px-4 py-3">
                  <ul className="text-xs space-y-1">
                    {o.items.map((i: any) => (
                      <li key={i.id} className="flex items-center gap-2">
                        <span className="font-medium text-slate-700">{i.medicine_name}</span>
                        <span className="text-slate-500">({i.dose} {i.frequency})</span>
                        <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                          Qty: {i.quantity_prescribed} → <b className={i.quantity_dispensed > 0 ? "text-emerald-600" : "text-slate-400"}>{i.quantity_dispensed}</b>
                        </span>
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${o.status === 'dispensed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {o.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {o.status === "pending" ? (
                    <button
                      onClick={() => dispense.mutate(o.id)}
                      disabled={dispense.isPending}
                      className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700 disabled:opacity-50"
                    >
                      Dispense
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400">Completed</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.length === 0 && <p className="p-6 text-center text-slate-500">No prescriptions found.</p>}
      </div>
    </div>
  );
}
''')

# ─── 3. FRONTEND: Update VisitTimeline (Doctor's View) ─────────────────
print("==> Updating VisitTimeline.tsx (Adding Pharmacy Card)")
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

old_lab_card = '''      <Card title="Lab orders">'''
new_lab_card = '''      <Card title="Pharmacy orders">
        {(t.pharm_orders as any[]).length === 0 ? (
          <p className="text-sm text-slate-500">No prescriptions.</p>
        ) : (
          <ul className="text-sm space-y-3">
            {(t.pharm_orders as any[]).map((o) => (
              <li key={o.id} className="flex justify-between items-start py-2 border-b last:border-0">
                <div className="w-full">
                  <div className="flex justify-between items-center w-full mb-1">
                    <span className="text-xs font-semibold text-slate-500 uppercase">Prescription</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${o.status === 'dispensed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                      {o.status}
                    </span>
                  </div>
                  <ul className="space-y-1 bg-slate-50 p-2 rounded border">
                    {o.items.map((i: any) => (
                      <li key={i.id} className="flex justify-between text-xs">
                        <span><b>{i.medicine_name}</b> ({i.dose} {i.frequency})</span>
                        <span className={i.quantity_dispensed > 0 ? "text-emerald-600 font-medium" : "text-slate-500"}>
                          {i.quantity_dispensed > 0 ? `Dispensed: ${i.quantity_dispensed}` : `Pending: ${i.quantity_prescribed}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Lab orders">'''

if old_lab_card in v:
    v = v.replace(old_lab_card, new_lab_card)
    vp.write_text(v, encoding="utf-8")
    print("   patched VisitTimeline.tsx")

print("==> Done. Refresh your browser.")