#!/usr/bin/env python3
"""
add_saas_features.py -- Implements Appointments UI, Stock UI, and Print Features.
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
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Fix Serializers for Stock and Users ───────────────────
print("==> Patching backend serializers and views")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

# Add medicine_name to StockSerializer
s = s.replace(
    '''class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ["id", "medicine", "batch_no", "expiry_date", "quantity"]
        read_only_fields = ["id"]''',
    '''class StockSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    class Meta:
        model = Stock
        fields = ["id", "medicine", "medicine_name", "batch_no", "expiry_date", "quantity"]
        read_only_fields = ["id"]'''
)
sp.write_text(s, encoding="utf-8")

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Add role filter to UserViewSet for the Appointment dropdown
v = v.replace(
    '''    def get_queryset(self):
        t = get_current_tenant() or self.request.user.tenant
        if t is None:
            return User.objects.none()
        return User.objects.filter(tenant=t)''',
    '''    def get_queryset(self):
        t = get_current_tenant() or self.request.user.tenant
        if t is None:
            return User.objects.none()
        qs = User.objects.filter(tenant=t)
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        return qs'''
)
vp.write_text(v, encoding="utf-8")

# ─── 2. FRONTEND: Add Print CSS ────────────────────────────────────────
print("==> Adding print CSS to index.css")
css_path = FRONTEND / "src" / "index.css"
css = css_path.read_text(encoding="utf-8")
if "@media print" not in css:
    css += '''
@media print {
  body * { visibility: hidden; }
  #print-area, #print-area * { visibility: visible; }
  #print-area { position: absolute; left: 0; top: 0; width: 100%; padding: 2rem; }
  .no-print { display: none !important; }
}
'''
    css_path.write_text(css, encoding="utf-8")

# ─── 3. FRONTEND: Create Appointments Page ─────────────────────────────
print("==> Creating Appointments.tsx")
write_frontend("src/pages/Appointments.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";
import { useNavigate } from "react-router-dom";

export default function Appointments() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [showForm, setShowForm] = useState(false);

  const appts = useQuery({
    queryKey: ["appointments"],
    queryFn: async () => (await api.get<Paginated<any>>("/appointments/")).data.results,
  });

  const patients = useQuery({
    queryKey: ["patients", "all"],
    queryFn: async () => (await api.get<Paginated<any>>("/patients/")).data.results,
  });

  const doctors = useQuery({
    queryKey: ["users", "doctors"],
    queryFn: async () => (await api.get<Paginated<any>>("/users/?role=doctor")).data.results,
  });

  const createAppt = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/appointments/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
      setShowForm(false);
    },
  });

  const checkIn = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post(`/appointments/${id}/check-in/`);
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["appointments"] });
      qc.invalidateQueries({ queryKey: ["visits"] });
      nav(`/visits/${data.visit_id}`);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    // Combine date and time
    const dateStr = fd.get("date");
    const timeStr = fd.get("time");
    const start = new Date(`${dateStr}T${timeStr}:00Z`).toISOString();
    const end = new Date(new Date(start).getTime() + 30 * 60000).toISOString(); // +30 mins

    createAppt.mutate({
      patient: Number(fd.get("patient")),
      doctor: Number(fd.get("doctor")),
      scheduled_start: start,
      scheduled_end: end,
      reason: String(fd.get("reason")),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Appointments</h1>
        <button onClick={() => setShowForm((v) => !v)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ Book Appointment</button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-lg p-6 space-y-4 shadow-sm max-w-2xl">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm">
              <span className="text-slate-600">Patient</span>
              <select name="patient" required className="mt-1 w-full border rounded px-3 py-2">
                <option value="">Select Patient...</option>
                {patients.data?.map((p: any) => <option key={p.id} value={p.id}>{p.full_name} ({p.mrn})</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Doctor</span>
              <select name="doctor" required className="mt-1 w-full border rounded px-3 py-2">
                <option value="">Select Doctor...</option>
                {doctors.data?.map((d: any) => <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name}</option>)}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Date</span>
              <input type="date" name="date" required className="mt-1 w-full border rounded px-3 py-2" />
            </label>
            <label className="text-sm">
              <span className="text-slate-600">Time</span>
              <input type="time" name="time" required className="mt-1 w-full border rounded px-3 py-2" />
            </label>
          </div>
          <label className="text-sm block">
            <span className="text-slate-600">Reason for visit</span>
            <input name="reason" className="mt-1 w-full border rounded px-3 py-2" placeholder="E.g. Routine checkup" />
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded text-slate-600 hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={createAppt.isPending} className="px-4 py-2 bg-sky-600 text-white rounded hover:bg-sky-700">Book</button>
          </div>
        </form>
      )}

      {appts.isLoading && <p className="text-slate-500">Loading...</p>}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Date & Time</th>
              <th className="text-left px-4 py-3">Patient</th>
              <th className="text-left px-4 py-3">Doctor</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {appts.data?.map((a: any) => (
              <tr key={a.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{new Date(a.scheduled_start).toLocaleString()}</td>
                <td className="px-4 py-3">{a.patient_name}</td>
                <td className="px-4 py-3">{a.doctor_name}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${a.status === 'scheduled' ? 'bg-sky-100 text-sky-700' : 'bg-emerald-100 text-emerald-700'}`}>{a.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  {a.status === "scheduled" && (
                    <button onClick={() => checkIn.mutate(a.id)} disabled={checkIn.isPending} className="bg-emerald-600 text-white text-xs px-3 py-1.5 rounded hover:bg-emerald-700">Check In</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

# ─── 4. FRONTEND: Create Stock Dashboard ───────────────────────────────
print("==> Creating StockDashboard.tsx")
write_frontend("src/pages/StockDashboard.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function StockDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["stock"],
    queryFn: async () => (await api.get<Paginated<any>>("/stock/")).data.results,
  });

  const isExpiring = (dateStr: string) => {
    const expiry = new Date(dateStr).getTime();
    const today = new Date().getTime();
    const days90 = 90 * 24 * 60 * 60 * 1000;
    return expiry - today < days90;
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Inventory & Stock Levels</h1>
      <p className="text-sm text-slate-500">Monitor batches and expiry dates. <span className="text-red-500 font-medium">Red</span> indicates low stock or near expiry.</p>

      {isLoading && <p className="text-slate-500">Loading...</p>}
      
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Medicine</th>
              <th className="text-left px-4 py-3">Batch No</th>
              <th className="text-left px-4 py-3">Expiry Date</th>
              <th className="text-left px-4 py-3">Qty Available</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.map((s: any) => {
              const lowStock = s.quantity < 50;
              const expiring = isExpiring(s.expiry_date);
              return (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{s.medicine_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{s.batch_no}</td>
                  <td className={`px-4 py-3 ${expiring ? "text-red-600 font-bold" : ""}`}>{s.expiry_date}</td>
                  <td className={`px-4 py-3 font-bold ${lowStock ? "text-red-600" : "text-slate-700"}`}>{s.quantity}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {data?.length === 0 && <p className="p-6 text-center text-slate-500">No stock records found.</p>}
      </div>
    </div>
  );
}
''')

# ─── 5. FRONTEND: Update Billing to print Receipt ──────────────────────
print("==> Updating BillingDashboard.tsx for Receipts")
bp = FRONTEND / "src" / "pages" / "BillingDashboard.tsx"
b = bp.read_text(encoding="utf-8")

# Add Print button and Print Area
old_bill_render = '''              <div className="flex justify-between font-medium text-emerald-600">
                <span>Balance Due</span>
                <span>ZMW {invoice.data.balance}</span>
              </div>

              {invoice.data.balance > 0 && ('''

new_bill_render = '''              <div className="flex justify-between font-medium text-emerald-600 border-b pb-4 mb-4">
                <span>Balance Due</span>
                <span>ZMW {invoice.data.balance}</span>
              </div>

              <button onClick={() => window.print()} className="w-full mb-4 bg-sky-100 text-sky-700 font-medium py-2 rounded hover:bg-sky-200">
                Print Receipt
              </button>

              {/* Printable Area (Hidden on screen, visible on print) */}
              <div id="print-area" className="hidden">
                <div className="text-center mb-6">
                  <h1 className="text-2xl font-bold">Nimbus OPD Cloud</h1>
                  <p className="text-sm">Official Receipt</p>
                </div>
                <div className="flex justify-between mb-4 text-sm">
                  <div>
                    <p><b>Receipt:</b> {invoice.data.invoice_no}</p>
                    <p><b>Patient:</b> {invoice.data.patient_name}</p>
                  </div>
                  <div className="text-right">
                    <p><b>Date:</b> {new Date().toLocaleDateString()}</p>
                  </div>
                </div>
                <table className="w-full text-sm mb-6">
                  <thead className="border-b">
                    <tr><th className="text-left py-2">Item</th><th className="text-right py-2">Amount</th></tr>
                  </thead>
                  <tbody>
                    {invoice.data.items.map((i: any) => (
                      <tr key={i.id}>
                        <td className="py-2">{i.quantity}x {i.description}</td>
                        <td className="text-right py-2">{i.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="border-t pt-2 text-right">
                  <p className="font-bold text-lg">Total: ZMW {invoice.data.total}</p>
                </div>
                <p className="text-center text-xs mt-12">Thank you for choosing Nimbus OPD.</p>
              </div>

              {invoice.data.balance > 0 && ('''

b = b.replace(old_bill_render, new_bill_render)
bp.write_text(b, encoding="utf-8")

# ─── 6. FRONTEND: Update VisitTimeline to print Prescription ───────────
print("==> Updating VisitTimeline.tsx for Prescriptions")
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

# Add print button next to Close Visit
old_header = '''        {t.status !== "closed" && (
          <button onClick={() => closeVisit.mutate()}
            disabled={closeVisit.isPending}
            className="ml-auto rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
            Close visit
          </button>
        )}'''
new_header = '''        <div className="ml-auto flex gap-2">
          <button onClick={() => window.print()} className="rounded bg-sky-100 text-sky-700 text-sm px-3 py-1.5 hover:bg-sky-200 font-medium">
            Print Prescription
          </button>
          {t.status !== "closed" && (
            <button onClick={() => closeVisit.mutate()}
              disabled={closeVisit.isPending}
              className="rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
              Close visit
            </button>
          )}
        </div>'''
v = v.replace(old_header, new_header)

# Add printable area at the very end of the component
old_end = '''      </Card>
    </div>
  );
}'''
new_end = '''      </Card>

      {/* Printable Prescription (Hidden on screen) */}
      <div id="print-area" className="hidden">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">Nimbus OPD Cloud</h1>
          <p className="text-sm">Prescription Slip</p>
        </div>
        <div className="mb-6">
          <p><b>Patient:</b> {t.patient.full_name} ({t.patient.mrn})</p>
          <p><b>Date:</b> {new Date(t.arrived_at).toLocaleDateString()}</p>
        </div>
        <div className="mb-6">
          <h3 className="font-bold border-b mb-2 pb-1">Diagnosis / Assessment</h3>
          <p className="text-sm">{t.notes[0]?.assessment || "N/A"}</p>
        </div>
        <div>
          <h3 className="font-bold border-b mb-2 pb-1">Medications</h3>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            {(t.pharm_orders as any[]).map((po: any) =>
              po.items.map((i: any) => (
                <li key={i.id}>
                  <b>{i.medicine_name}</b> - {i.dose} {i.frequency} for {i.duration_days} days ({i.quantity_prescribed} total)
                </li>
              ))
            )}
          </ul>
        </div>
        <div className="mt-16 pt-8 border-t text-center text-xs">
          <p>Doctor Signature: ____________________</p>
        </div>
      </div>
    </div>
  );
}'''
v = v.replace(old_end, new_end)
vp.write_text(v, encoding="utf-8")

# ─── 7. FRONTEND: Routing & Navigation ─────────────────────────────────
print("==> Updating Navigation and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")

if "Appointments" not in l:
    l = l.replace(
        '<NavLink to="/patients" className={linkClass}>Patients</NavLink>',
        '<NavLink to="/patients" className={linkClass}>Patients</NavLink>\n'
        '            {user?.role === "receptionist" || user?.role === "admin" ? (\n'
        '              <NavLink to="/appointments" className={linkClass}>Appointments</NavLink>\n'
        '            ) : null}'
    )
    l = l.replace(
        '<NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>',
        '<NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>\n'
        '            {user?.role === "pharmacist" || user?.role === "admin" ? (\n'
        '              <NavLink to="/stock" className={linkClass}>Stock</NavLink>\n'
        '            ) : null}'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "Appointments" not in a:
    a = a.replace(
        'import BillingDashboard from "./pages/BillingDashboard";',
        'import BillingDashboard from "./pages/BillingDashboard";\nimport Appointments from "./pages/Appointments";\nimport StockDashboard from "./pages/StockDashboard";'
    )
    a = a.replace(
        '<Route path="/billing" element={<BillingDashboard />} />',
        '<Route path="/billing" element={<BillingDashboard />} />\n          <Route path="/appointments" element={<Appointments />} />\n          <Route path="/stock" element={<StockDashboard />} />'
    )
    ap.write_text(a, encoding="utf-8")

print("==> Done. Refresh your browser.")