#!/usr/bin/env python3
"""
fix_platform_billing_table.py -- Fix pagination loop and add Date Joined column.
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

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Fix the paginated list loop ───────────────────────────
print("==> Patching api/platform_views.py")
pv = ROOT / "api" / "platform_views.py"
v = pv.read_text(encoding="utf-8")

old_list = '''    def list(self, request, *args, **kwargs):
        from django.utils import timezone
        from datetime import timedelta
        import random

        response = super().list(request, *args, **kwargs)
        # Inject mock billing data for the UI
        for clinic in response.data:
            # Mock logic: Active clinics have paid, Pending haven't
            if clinic["is_active"]:
                clinic["billing_status"] = "paid"
                clinic["plan"] = "Pro (K3,500/mo)"
                # Mock next billing date (30 days from creation)
                created = timezone.datetime.fromisoformat(clinic["created_at"].replace("Z", "+00:00"))
                clinic["next_billing"] = (created + timedelta(days=30)).strftime("%Y-%m-%d")
            else:
                clinic["billing_status"] = "pending"
                clinic["plan"] = "Starter (K1,250/mo)"
                clinic["next_billing"] = "Awaiting Payment"

        return response'''

new_list = '''    def list(self, request, *args, **kwargs):
        from django.utils.dateparse import parse_datetime
        from datetime import timedelta

        response = super().list(request, *args, **kwargs)
        
        # Handle Pagination correctly
        if isinstance(response.data, dict) and "results" in response.data:
            clinics = response.data["results"]
        else:
            clinics = response.data

        for clinic in clinics:
            if clinic.get("is_active"):
                clinic["billing_status"] = "paid"
                clinic["plan"] = "Pro (K3,500/mo)"
                # Calculate next billing date safely
                created_str = clinic.get("created_at")
                if created_str:
                    created = parse_datetime(created_str)
                    clinic["next_billing"] = (created + timedelta(days=30)).strftime("%Y-%m-%d") if created else "N/A"
                else:
                    clinic["next_billing"] = "N/A"
            else:
                clinic["billing_status"] = "pending"
                clinic["plan"] = "Starter (K1,250/mo)"
                clinic["next_billing"] = "Awaiting Payment"

        return response'''

if old_list in v:
    v = v.replace(old_list, new_list)
    pv.write_text(v, encoding="utf-8")
    print("   patched platform_views.py")
else:
    print("   [WARN] Could not find old list method.")

# ─── 2. FRONTEND: Add Date Joined to table ─────────────────────────────
print("==> Updating PlatformAdminDashboard.tsx")
write_frontend("src/pages/PlatformAdminDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PlatformAdminDashboard() {
  const qc = useQueryClient();

  const stats = useQuery({
    queryKey: ["platform-stats"],
    queryFn: async () => (await api.get("/platform/stats/")).data,
  });

  const clinics = useQuery({
    queryKey: ["platform-clinics"],
    queryFn: async () => (await api.get<Paginated<any>>("/platform/clinics/")).data.results,
  });

  const approve = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/platform/clinics/${id}/approve/`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform-clinics"] });
      qc.invalidateQueries({ queryKey: ["platform-stats"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Billing & Administration</h1>
          <p className="text-sm text-slate-500 mt-1">Manage clinic subscriptions, payments, and approvals.</p>
        </div>
      </div>

      {stats.data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Active Subscriptions" value={stats.data.active_clinics} color="text-emerald-600" />
          <Stat label="Pending Approvals" value={stats.data.pending_clinics} color="text-amber-600" />
          <Stat label="Current MRR" value={`K ${stats.data.mrr_zmw.toLocaleString()}`} />
          <Stat label="Total Clinics" value={stats.data.total_clinics} />
        </div>
      )}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <div className="bg-slate-50 px-4 py-3 border-b font-semibold text-slate-700">Clinic Subscriptions</div>
        <table className="w-full text-sm">
          <thead className="text-slate-500 bg-white">
            <tr>
              <th className="text-left px-4 py-3">Clinic Name</th>
              <th className="text-left px-4 py-3">Date Joined</th>
              <th className="text-left px-4 py-3">Plan</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Billing Status</th>
              <th className="text-left px-4 py-3">Next Billing</th>
              <th className="text-right px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {clinics.data?.map((c: any) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">
                  {c.name}
                  <span className="block text-xs text-slate-400 font-normal mt-0.5">{c.code}</span>
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {new Date(c.created_at).toLocaleDateString(undefined, {
                    year: 'numeric', month: 'short', day: 'numeric'
                  })}
                </td>
                <td className="px-4 py-3 text-slate-600">{c.plan}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.is_active ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-600'}`}>
                    {c.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-bold ${c.billing_status === 'paid' ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {c.billing_status === 'paid' ? 'PAID' : 'PENDING'}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">{c.next_billing}</td>
                <td className="px-4 py-3 text-right">
                  {!c.is_active ? (
                    <button onClick={() => approve.mutate(c.id)} disabled={approve.isPending} className="bg-emerald-600 text-white text-xs px-3 py-1.5 rounded hover:bg-emerald-700 shadow-sm transition">
                      Approve & Activate
                    </button>
                  ) : (
                    <button className="bg-slate-100 text-slate-500 text-xs px-3 py-1.5 rounded cursor-not-allowed">
                      Manage Billing
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {clinics.data?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No clinics found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, color = "text-slate-800" }: { label: string, value: string | number, color?: string }) {
  return (
    <div className="bg-white border rounded-lg p-5 shadow-sm">
      <p className="text-sm text-slate-500 font-medium">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
''')

print("==> Done. Restart your Django server and refresh.")