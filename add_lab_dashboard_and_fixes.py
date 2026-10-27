#!/usr/bin/env python3
"""
add_lab_dashboard_and_fixes.py -- Fix Lab Queue filtering, hide buttons on completed, and add Lab Dashboard.
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

# ─── 1. BACKEND: Fix LabOrderViewSet Filtering ─────────────────────────
print("==> Patching api/views.py (LabOrderViewSet status filtering)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_lab_qs = '''class LabOrderViewSet(TenantScopedViewSet):
    serializer_class = LabOrderSerializer
    queryset = LabOrder.objects.all()
    permission_classes = [require_roles("admin", "lab", "doctor")]'''

new_lab_qs = '''class LabOrderViewSet(TenantScopedViewSet):
    serializer_class = LabOrderSerializer
    permission_classes = [require_roles("admin", "lab", "doctor")]

    def get_queryset(self):
        qs = LabOrder.objects.all()
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs'''

if old_lab_qs in v:
    v = v.replace(old_lab_qs, new_lab_qs)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py")
else:
    print("   [WARN] Could not find LabOrderViewSet block to patch.")

# ─── 2. FRONTEND: Update LabDashboard to hide button if completed ──────
print("==> Patching src/pages/LabDashboard.tsx")
ldp = FRONTEND / "src" / "pages" / "LabDashboard.tsx"
ld = ldp.read_text(encoding="utf-8")

old_btn = '''                  <button
                    onClick={() => setActiveOrder(o)}
                    className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700"
                  >
                    Record Result
                  </button>'''

new_btn = '''                  {o.status === "pending" ? (
                    <button
                      onClick={() => setActiveOrder(o)}
                      className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700"
                    >
                      Record Result
                    </button>
                  ) : (
                    <span className="text-xs text-slate-400 font-medium">Completed</span>
                  )}'''

if old_btn in ld:
    ld = ld.replace(old_btn, new_btn)
    ldp.write_text(ld, encoding="utf-8")
    print("   patched LabDashboard.tsx")

# ─── 3. FRONTEND: Create LabTechDashboard ──────────────────────────────
print("==> Creating LabTechDashboard component")
write_frontend("src/pages/LabTechDashboard.tsx", '''\
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function LabTechDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["lab-orders", "dashboard"],
    queryFn: async () => (await api.get<Paginated<any>>("/lab-orders/")).data.results,
  });

  if (isLoading) return <p className="text-slate-500">Loading summary…</p>;

  const pending = data?.filter((o: any) => o.status === "pending") || [];
  const completed = data?.filter((o: any) => o.status === "completed") || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Laboratory Overview</h1>
        <Link to="/lab" className="bg-sky-600 text-white px-4 py-2 rounded text-sm hover:bg-sky-700">
          Go to Lab Queue →
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard title="Pending Tests" value={pending.length} color="amber" />
        <StatCard title="Completed Tests" value={completed.length} color="emerald" />
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-700 mb-2">Recent Completed Tests</h2>
        <p className="text-sm text-slate-500 mb-4">The last 5 results recorded by the lab.</p>
        <ul className="divide-y text-sm">
          {completed.slice(0, 5).map((o: any) => (
            <li key={o.id} className="py-3 flex justify-between items-center">
              <div>
                <p className="font-medium text-slate-800">{o.patient_name || o.visit_no}</p>
                <p className="text-xs text-slate-500">
                  {o.test_name} {o.result ? `(Result: ${o.result.value_text} ${o.result.unit})` : ""}
                </p>
              </div>
              <span className="text-xs text-slate-400">
                {new Date(o.completed_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
          {completed.length === 0 && <li className="py-4 text-slate-500 text-center">No completed tests yet.</li>}
        </ul>
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: { title: string, value: number, color: string }) {
  const colors: any = {
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
  };
  return (
    <div className={`border rounded-lg p-5 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
    </div>
  );
}
''')

# ─── 4. FRONTEND: Route Dashboard to LabTechDashboard ──────────────────
print("==> Updating Dashboard.tsx")
dp = FRONTEND / "src" / "pages" / "Dashboard.tsx"
d = dp.read_text(encoding="utf-8")

# Add import
if "LabTechDashboard" not in d:
    d = d.replace(
        'import PharmacistDashboard from "./PharmacistDashboard";',
        'import PharmacistDashboard from "./PharmacistDashboard";\nimport LabTechDashboard from "./LabTechDashboard";'
    )

# Add render logic
old_lab_redirect = '''  if (user?.role === "lab") {
    return <Navigate to="/lab" replace />;
  }'''
new_lab_redirect = '''  if (user?.role === "lab") {
    return <LabTechDashboard />;
  }'''

if old_lab_redirect in d:
    d = d.replace(old_lab_redirect, new_lab_redirect)
    dp.write_text(d, encoding="utf-8")
    print("   patched Dashboard.tsx")
else:
    print("   [WARN] Could not find lab redirect logic. Checking fallback...")
    # If the earlier script changed it to return <Navigate>, try that
    d = d.replace(
        'if (user?.role === "lab") {\n    return <Navigate to="/lab" replace />;\n  }',
        'if (user?.role === "lab") {\n    return <LabTechDashboard />;\n  }'
    )
    if "LabTechDashboard />" in d:
         dp.write_text(d, encoding="utf-8")
         print("   patched Dashboard.tsx (fallback method)")

print("==> Done. Restart the Django server and refresh your browser.")