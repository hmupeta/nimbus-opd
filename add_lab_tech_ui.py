#!/usr/bin/env python3
"""
add_lab_tech_ui.py -- Add Lab Dashboard for technicians and result rendering for doctors.
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


# ─── 1. BACKEND: Update LabOrderSerializer to include the Result ───────
print("==> Patching api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

# Ensure LabResultSerializer is defined before LabOrderSerializer
if "class LabResultSerializer" not in s:
    print("   [WARN] LabResultSerializer not found, skipping patch.")
else:
    old_serializer = '''class LabOrderSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    test_code = serializers.CharField(source="test.code", read_only=True)

    class Meta:
        model = LabOrder
        fields = ["id", "visit", "order", "test", "test_name", "test_code", "status",
                  "ordered_at", "collected_at", "completed_at", "collected_by"]
        read_only_fields = ["id", "ordered_at", "collected_at",
                            "completed_at", "collected_by"]'''

    new_serializer = '''class LabOrderSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    test_code = serializers.CharField(source="test.code", read_only=True)
    result = LabResultSerializer(read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)

    class Meta:
        model = LabOrder
        fields = ["id", "visit", "order", "test", "test_name", "test_code", "status",
                  "patient_name", "result",
                  "ordered_at", "collected_at", "completed_at", "collected_by"]
        read_only_fields = ["id", "ordered_at", "collected_at",
                            "completed_at", "collected_by"]'''

    if old_serializer in s:
        s = s.replace(old_serializer, new_serializer)
        sp.write_text(s, encoding="utf-8")
        print("   patched api/serializers.py")

# ─── 2. FRONTEND: Update Types ─────────────────────────────────────────
print("==> Updating frontend types")
tp = FRONTEND / "src" / "api" / "types.ts"
t = tp.read_text(encoding="utf-8")

if "interface LabResult" not in t:
    t = t.replace(
        "export interface LabOrder {",
        '''export interface LabResult {
  id: number;
  value_text: string;
  unit: string;
  flag: string;
  comment: string;
  resulted_at: string;
}

export interface LabOrder {'''
    )
    t = t.replace(
        "  test_code: string;",
        "  test_code: string;\n  patient_name: string;\n  result: LabResult | null;"
    )
    tp.write_text(t, encoding="utf-8")

# ─── 3. FRONTEND: Create LabDashboard ──────────────────────────────────
print("==> Creating LabDashboard page")
write_frontend("src/pages/LabDashboard.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated, LabOrder } from "../api/types";

export default function LabDashboard() {
  const qc = useQueryClient();
  const [activeOrder, setActiveOrder] = useState<LabOrder | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["lab-orders", "pending"],
    queryFn: async () =>
      (await api.get<Paginated<LabOrder>>("/lab-orders/?status=pending")).data,
  });

  const submitResult = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: any }) => {
      await api.post(`/lab-orders/${id}/result/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lab-orders"] });
      setActiveOrder(null);
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!activeOrder) return;
    const fd = new FormData(e.currentTarget);
    submitResult.mutate({
      id: activeOrder.id,
      payload: {
        value_text: String(fd.get("value_text") || ""),
        unit: String(fd.get("unit") || ""),
        flag: String(fd.get("flag") || "normal"),
        comment: String(fd.get("comment") || ""),
      },
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Laboratory Queue</h1>

      {isLoading && <p className="text-slate-500">Loading…</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Order Time</th>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Test</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.results.map((o) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-500">
                  {new Date(o.ordered_at).toLocaleTimeString()}
                </td>
                <td className="px-4 py-3 font-medium">{o.patient_name}</td>
                <td className="px-4 py-3">
                  {o.test_name} <span className="text-xs text-slate-400 font-mono">({o.test_code})</span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
                    {o.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => setActiveOrder(o)}
                    className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700"
                  >
                    Record Result
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.results.length === 0 && (
          <p className="p-6 text-center text-slate-500">No pending lab tests.</p>
        )}
      </div>

      {activeOrder && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="font-semibold text-lg">Record Result</h2>
              <button onClick={() => setActiveOrder(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={onSubmit} className="p-4 space-y-4">
              <div className="bg-slate-50 p-3 rounded text-sm mb-4">
                <p><span className="text-slate-500">Patient:</span> <b>{activeOrder.patient_name}</b></p>
                <p><span className="text-slate-500">Test:</span> <b>{activeOrder.test_name}</b></p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <label className="block text-sm">
                  <span className="text-slate-600">Result Value *</span>
                  <input name="value_text" required className="mt-1 w-full border rounded px-3 py-2" />
                </label>
                <label className="block text-sm">
                  <span className="text-slate-600">Unit</span>
                  <input name="unit" defaultValue={activeOrder.test_code === "CBC" ? "10^9/L" : ""} className="mt-1 w-full border rounded px-3 py-2" />
                </label>
              </div>
              <label className="block text-sm">
                <span className="text-slate-600">Flag</span>
                <select name="flag" className="mt-1 w-full border rounded px-3 py-2">
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="low">Low</option>
                  <option value="critical">Critical</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-slate-600">Comments</span>
                <textarea name="comment" rows={2} className="mt-1 w-full border rounded px-3 py-2" />
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setActiveOrder(null)} className="px-4 py-2 text-sm text-slate-600 border rounded hover:bg-slate-50">Cancel</button>
                <button type="submit" disabled={submitResult.isPending} className="px-4 py-2 text-sm text-white bg-emerald-600 rounded hover:bg-emerald-700">
                  {submitResult.isPending ? "Saving..." : "Save Result"}
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

# ─── 4. FRONTEND: Update VisitTimeline for Doctor view ─────────────────
print("==> Updating VisitTimeline.tsx to show Results")
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

old_lab_card = '''      <Card title="Lab orders">
        {t.lab_orders.length === 0 ? (
          <p className="text-sm text-slate-500">No lab orders.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {t.lab_orders.map((l) => (
              <li key={l.id} className="flex justify-between items-center py-1 border-b last:border-0">
                <div>
                  <span className="font-medium text-slate-700">{l.test_name}</span>
                  <span className="ml-2 text-xs text-slate-400 font-mono">{l.test_code}</span>
                </div>
                <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{l.status}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>'''

new_lab_card = '''      <Card title="Lab orders">
        {t.lab_orders.length === 0 ? (
          <p className="text-sm text-slate-500">No lab orders.</p>
        ) : (
          <ul className="text-sm space-y-2">
            {t.lab_orders.map((l) => (
              <li key={l.id} className="flex justify-between items-start py-2 border-b last:border-0">
                <div>
                  <span className="font-medium text-slate-700">{l.test_name}</span>
                  <span className="ml-2 text-xs text-slate-400 font-mono">{l.test_code}</span>
                  {l.result && (
                    <div className="mt-1 text-xs text-slate-600 bg-slate-50 p-2 rounded border">
                      <p>Result: <b>{l.result.value_text} {l.result.unit}</b></p>
                      <p>Flag: <b className={l.result.flag !== "normal" ? "text-red-600" : "text-emerald-600"}>{l.result.flag.toUpperCase()}</b></p>
                      {l.result.comment && <p>Comment: {l.result.comment}</p>}
                    </div>
                  )}
                </div>
                <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded ml-2">{l.status}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>'''

if old_lab_card in v:
    v = v.replace(old_lab_card, new_lab_card)
    vp.write_text(v, encoding="utf-8")

# ─── 5. FRONTEND: Update Layout & Router ───────────────────────────────
print("==> Updating Navigation and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Lab Queue" not in l:
    l = l.replace(
        '<NavLink to="/patients" className={linkClass}>Patients</NavLink>',
        '<NavLink to="/patients" className={linkClass}>Patients</NavLink>\n'
        '            {user?.role === "lab" || user?.role === "admin" ? (\n'
        '              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>\n'
        '            ) : null}'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "LabDashboard" not in a:
    a = a.replace(
        'import VisitTimeline from "./pages/VisitTimeline";',
        'import VisitTimeline from "./pages/VisitTimeline";\nimport LabDashboard from "./pages/LabDashboard";'
    )
    a = a.replace(
        '<Route path="/visits/:id" element={<VisitTimeline />} />',
        '<Route path="/visits/:id" element={<VisitTimeline />} />\n          <Route path="/lab" element={<LabDashboard />} />'
    )
    ap.write_text(a, encoding="utf-8")

print("==> Done.")