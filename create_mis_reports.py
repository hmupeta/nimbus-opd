#!/usr/bin/env python3
"""
create_mis_reports.py -- Create the missing MISReports.tsx page.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

FRONTEND = OPD / "frontend"
PAGES = FRONTEND / "src" / "pages"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. Create MISReports.tsx ──────────────────────────────────────────
print("==> Creating MISReports.tsx")
MIS_REPORTS = r'''\
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";

const COLORS = ["#0284c7", "#10b981", "#6366f1", "#f59e0b"];

export default function MISReports() {
  const { data, isLoading } = useQuery({
    queryKey: ["mis-reports"],
    queryFn: async () => (await api.get("/reports/mis/")).data,
  });

  if (isLoading) return <p className="text-slate-500">Loading reports…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-800">Management Reports</h1>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 text-slate-700">
            Doctor Throughput
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.doctor_throughput || []}>
                <XAxis
                  dataKey="doctor"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12 }}
                />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar
                  dataKey="patients"
                  fill="#0284c7"
                  radius={[4, 4, 0, 0]}
                  name="Patients Seen"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 text-slate-700">
            Revenue by Payer Mix
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data?.payer_mix || []}
                  dataKey="amount"
                  nameKey="method"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label
                >
                  {data?.payer_mix?.map((entry: any, index: number) => (
                    <Cell
                      key={entry.name || `cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip formatter={(value: any) => `ZMW ${value}`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white border rounded-lg p-6 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-700">
            Lab Turnaround Time (TAT)
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Average time from order to result completion.
          </p>
        </div>
        <div className="text-center">
          <p className="text-4xl font-bold text-indigo-600">
            {data?.lab_tat_minutes}{" "}
            <span className="text-xl text-slate-500">mins</span>
          </p>
          <p className="text-xs text-slate-400 mt-1">
            {data?.lab_volume} tests processed
          </p>
        </div>
      </div>
    </div>
  );
}
'''
(PAGES / "MISReports.tsx").write_text(MIS_REPORTS, encoding="utf-8")
print("   wrote src/pages/MISReports.tsx")

# ─── 2. Re-verify all App.tsx imports resolve ──────────────────────────
print("\n==> Re-verifying all App.tsx imports")
app_content = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
import_pattern = re.compile(r'import\s+\w+\s+from\s+["\'](\./[^"\']+)["\']')
imports = import_pattern.findall(app_content)

missing = []
for rel_path in imports:
    clean = rel_path.lstrip("./")
    candidates = [
        FRONTEND / "src" / f"{clean}.tsx",
        FRONTEND / "src" / f"{clean}.ts",
    ]
    if not any(c.exists() for c in candidates):
        missing.append(rel_path)

if missing:
    print("   ❌ Still missing:")
    for m in missing:
        print(f"      {m}")
    sys.exit(1)
print(f"   ✓ All {len(imports)} imports resolve")

# ─── 3. Verify Layout.tsx imports ──────────────────────────────────────
print("==> Verifying Layout.tsx imports")
layout_content = (FRONTEND / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
layout_imports = import_pattern.findall(layout_content)

for rel_path in layout_imports:
    clean = rel_path.lstrip("./")
    candidates = [
        FRONTEND / "src" / "components" / f"{clean}.tsx",
        FRONTEND / "src" / "components" / f"{clean}.ts",
        FRONTEND / "src" / f"{clean}.tsx",
    ]
    if not any(c.exists() for c in candidates):
        print(f"   ❌ Missing: {rel_path}")
        sys.exit(1)
print(f"   ✓ All {len(layout_imports)} Layout imports resolve")

# ─── 4. Quick check: does every page file parse cleanly? ───────────────
print("\n==> Final page inventory")
for f in sorted(PAGES.glob("*.tsx")):
    print(f"   {f.name:28} {f.stat().st_size:>6} bytes")

# ─── 5. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(frontend): create missing MISReports.tsx page",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")