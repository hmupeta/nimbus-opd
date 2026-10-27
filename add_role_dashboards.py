#!/usr/bin/env python3
"""
add_role_dashboards.py -- Fix blank dashboard for Pharmacists and Receptionists.
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

# ─── 1. Create Pharmacist Dashboard ────────────────────────────────────
print("==> Creating PharmacistDashboard component")
write_frontend("src/pages/PharmacistDashboard.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacistDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-orders", "dashboard"],
    queryFn: async () => (await api.get<Paginated<any>>("/pharmacy-orders/")).data.results,
  });

  if (isLoading) return <p className="text-slate-500">Loading summary…</p>;

  const pending = data?.filter((o: any) => o.status === "pending") || [];
  const dispensed = data?.filter((o: any) => o.status === "dispensed") || [];
  
  // Calculate total drugs handed out
  const totalItemsDispensed = dispensed.reduce((acc: number, o: any) => {
    return acc + o.items.reduce((sum: number, i: any) => sum + i.quantity_dispensed, 0);
  }, 0);

  // Unique patients served (by visit ID)
  const uniquePatients = new Set(dispensed.map((o: any) => o.visit_no)).size;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Pharmacy Overview</h1>
        <Link to="/pharmacy" className="bg-sky-600 text-white px-4 py-2 rounded text-sm hover:bg-sky-700">
          Go to Dispensing Queue →
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Pending Prescriptions" value={pending.length} color="amber" />
        <StatCard title="Patients Served" value={uniquePatients} color="emerald" />
        <StatCard title="Total Drugs Dispensed" value={totalItemsDispensed} color="sky" />
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-700 mb-2">Recent Dispensations</h2>
        <p className="text-sm text-slate-500 mb-4">The last 5 completed orders.</p>
        <ul className="divide-y text-sm">
          {dispensed.slice(0, 5).map((o: any) => (
            <li key={o.id} className="py-3 flex justify-between items-center">
              <div>
                <p className="font-medium text-slate-800">{o.patient_name || o.visit_no}</p>
                <p className="text-xs text-slate-500">
                  {o.items.map((i: any) => `${i.quantity_dispensed}x ${i.medicine_name}`).join(", ")}
                </p>
              </div>
              <span className="text-xs text-slate-400">
                {new Date(o.dispensed_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
          {dispensed.length === 0 && <li className="py-4 text-slate-500 text-center">No dispensations yet.</li>}
        </ul>
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: { title: string, value: number, color: string }) {
  const colors: any = {
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
    sky: "bg-sky-50 border-sky-200 text-sky-700",
  };
  return (
    <div className={`border rounded-lg p-5 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
    </div>
  );
}
''')

# ─── 2. Update Dashboard to Route Based on Role ────────────────────────
print("==> Updating Dashboard.tsx for role-based routing")
dp = FRONTEND / "src" / "pages" / "Dashboard.tsx"
d = dp.read_text(encoding="utf-8")

# Replace the existing lab check with a comprehensive role router
old_redirect = '''export default function Dashboard() {
  const user = currentUser();
  if (user?.role === "lab") {
    return <Navigate to="/lab" replace />;
  }

  const summary = useQuery({'''

new_redirect = '''import PharmacistDashboard from "./PharmacistDashboard";

export default function Dashboard() {
  const user = currentUser();
  
  if (user?.role === "lab") {
    return <Navigate to="/lab" replace />;
  }
  if (user?.role === "pharmacist") {
    return <PharmacistDashboard />;
  }
  if (user?.role === "receptionist") {
    return <Navigate to="/billing" replace />;
  }

  const summary = useQuery({'''

if old_redirect in d:
    d = d.replace(old_redirect, new_redirect)
    dp.write_text(d, encoding="utf-8")
    print("   patched Dashboard.tsx")
else:
    print("   [WARN] Could not find Dashboard redirect block. Checking if already patched...")
    if "PharmacistDashboard" not in d:
        # Fallback: just inject the import and role check manually if formatting differs
        d = d.replace('import { currentUser } from "../api/auth";', 'import { currentUser } from "../api/auth";\nimport PharmacistDashboard from "./PharmacistDashboard";')
        d = d.replace(
            'if (user?.role === "lab") {', 
            'if (user?.role === "pharmacist") return <PharmacistDashboard />;\n  if (user?.role === "receptionist") return <Navigate to="/billing" replace />;\n  if (user?.role === "lab") {'
        )
        dp.write_text(d, encoding="utf-8")
        print("   patched Dashboard.tsx (fallback method)")

print("==> Done. Refresh your browser.")