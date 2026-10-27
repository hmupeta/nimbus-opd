#!/usr/bin/env python3
"""
fix_workflow_queues.py -- Split Dashboard into Nursing and Doctor queues, and add workflow prompts.
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

# ─── 1. Update Dashboard.tsx to show Queues ────────────────────────────
print("==> Rewriting Dashboard.tsx")
write_frontend("src/pages/Dashboard.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { api } from "../api/client";
import { currentUser } from "../api/auth";
import type { DashboardSummary, Paginated, Visit } from "../api/types";
import PharmacistDashboard from "./PharmacistDashboard";
import LabTechDashboard from "./LabTechDashboard";

export default function Dashboard() {
  const user = currentUser();
  
  if (user?.role === "lab") return <LabTechDashboard />;
  if (user?.role === "pharmacist") return <PharmacistDashboard />;
  if (user?.role === "receptionist") return <Navigate to="/billing" replace />;
  if (user?.role === "radiology") return <Navigate to="/radiology" replace />;

  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get<DashboardSummary>("/reports/dashboard/")).data,
  });

  const visits = useQuery({
    queryKey: ["visits", "active"],
    queryFn: async () => {
      const activeStatuses = ["open", "triaged", "in_consultation"];
      const results = await Promise.all(
        activeStatuses.map((s) =>
          api.get<Paginated<Visit>>(`/visits/?status=${s}`).then((r) => r.data.results)
        )
      );
      return results.flat();
    },
  });

  const nursingQueue = visits.data?.filter((v) => v.status === "open") || [];
  const doctorQueue = visits.data?.filter((v) => v.status === "triaged" || v.status === "in_consultation") || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Clinic Dashboard</h1>

      {summary.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Today's visits" value={summary.data.census.total} />
          <Stat label="Waiting for Nurse" value={nursingQueue.length} />
          <Stat label="Waiting for Doctor" value={doctorQueue.length} />
          <Stat label="Revenue today" value={`ZMW ${summary.data.revenue.today}`} />
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Nursing Queue */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-lg font-semibold text-sky-800">Nursing Queue</h2>
            <span className="bg-sky-100 text-sky-700 text-xs px-2 py-0.5 rounded-full">{nursingQueue.length}</span>
          </div>
          <p className="text-sm text-slate-500 mb-3">Patients waiting for vitals (Status: Open)</p>
          <ul className="divide-y border rounded-lg bg-white">
            {nursingQueue.map((v) => (
              <li key={v.id}>
                <Link to={`/visits/${v.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <div>
                    <p className="font-medium">{v.patient_name}</p>
                    <p className="text-sm text-slate-500">{v.visit_no} · {new Date(v.arrived_at).toLocaleTimeString()}</p>
                  </div>
                  <span className="text-xs bg-sky-100 text-sky-700 rounded px-2 py-0.5 font-medium">Record Vitals →</span>
                </Link>
              </li>
            ))}
            {nursingQueue.length === 0 && <li className="p-4 text-slate-500 text-sm text-center">No patients waiting.</li>}
          </ul>
        </section>

        {/* Doctor's Queue */}
        <section>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-lg font-semibold text-emerald-800">Doctor's Queue</h2>
            <span className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full">{doctorQueue.length}</span>
          </div>
          <p className="text-sm text-slate-500 mb-3">Patients ready for consultation (Status: Triaged)</p>
          <ul className="divide-y border rounded-lg bg-white">
            {doctorQueue.map((v) => (
              <li key={v.id}>
                <Link to={`/visits/${v.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
                  <div>
                    <p className="font-medium">{v.patient_name}</p>
                    <p className="text-sm text-slate-500">{v.visit_no}</p>
                  </div>
                  <span className={`text-xs rounded px-2 py-0.5 font-medium ${v.status === 'triaged' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                    {v.status === 'triaged' ? 'Start Consult →' : 'In Consult'}
                  </span>
                </Link>
              </li>
            ))}
            {doctorQueue.length === 0 && <li className="p-4 text-slate-500 text-sm text-center">No patients waiting.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}
''')

# ─── 2. Add visual prompt in VisitTimeline ─────────────────────────────
print("==> Updating VisitTimeline.tsx to prompt nurse")
vp = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
v = vp.read_text(encoding="utf-8")

# Add a banner at the top of the header if status is 'open'
old_header = '''      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-sky-700">← Dashboard</Link>
        <h1 className="text-2xl font-semibold">
          {t.visit_no} — {t.patient.full_name}
        </h1>
        <span className="text-xs bg-sky-100 text-sky-700 rounded px-2 py-0.5">
          {t.status}
        </span>
        {t.status !== "closed" && (
          <button onClick={() => closeVisit.mutate()}
            disabled={closeVisit.isPending}
            className="ml-auto rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
            Close visit
          </button>
        )}
      </div>'''

new_header = '''      <div className="flex items-center gap-3">
        <Link to="/" className="text-sm text-sky-700">← Dashboard</Link>
        <h1 className="text-2xl font-semibold">
          {t.visit_no} — {t.patient.full_name}
        </h1>
        <span className={`text-xs rounded px-2 py-0.5 ${t.status === 'open' ? 'bg-amber-100 text-amber-700' : 'bg-sky-100 text-sky-700'}`}>
          {t.status}
        </span>
        {t.status !== "closed" && (
          <button onClick={() => closeVisit.mutate()}
            disabled={closeVisit.isPending}
            className="ml-auto rounded bg-slate-700 text-white text-sm px-3 py-1.5 hover:bg-slate-800 disabled:opacity-50">
            Close visit
          </button>
        )}
      </div>

      {t.status === "open" && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 p-4 rounded-lg flex items-center justify-between shadow-sm">
          <div>
            <p className="font-semibold">Action Required</p>
            <p className="text-sm">This patient needs their vitals recorded before the doctor can see them.</p>
          </div>
          {canRecordVitals && !showVitalsForm && (
            <button onClick={() => setShowVitalsForm(true)} className="bg-amber-600 text-white px-4 py-2 rounded shadow hover:bg-amber-700 text-sm font-medium">
              Record Vitals Now
            </button>
          )}
        </div>
      )}'''

if old_header in v:
    v = v.replace(old_header, new_header)
    vp.write_text(v, encoding="utf-8")
    print("   patched VisitTimeline.tsx")

print("==> Done. Refresh your browser.")