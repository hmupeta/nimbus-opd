#!/usr/bin/env python3
"""
fix_order_sync_and_pharmacy.py
  - Adds Django signals to auto-sync parent Order status when Lab/Rad/Pharm finishes.
  - Backfills existing stuck parent orders.
  - Updates PharmacyDashboard.tsx to show a clear alert when dispense fails.
"""
from __future__ import annotations
import os
import shutil
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

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Create Signals for Auto-Sync ──────────────────────────
print("==> Creating clinical/signals.py")
write("clinical/signals.py", '''\
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder

def _check_and_complete_parent_order(sub_order):
    """If all sub-orders for a parent are completed, mark the parent as completed."""
    parent = sub_order.order
    if not parent:
        return
    
    if parent.status == Order.Status.COMPLETED:
        return
        
    all_done = True
    if parent.kind == Order.Kind.LAB:
        subs = LabOrder.all_objects.filter(order=parent)
        all_done = all(s.status in ["completed", "cancelled"] for s in subs)
    elif parent.kind == Order.Kind.RADIOLOGY:
        subs = RadiologyOrder.all_objects.filter(order=parent)
        all_done = all(s.status in ["reported", "cancelled"] for s in subs)
    elif parent.kind == Order.Kind.PHARMACY:
        subs = PharmacyOrder.all_objects.filter(order=parent)
        all_done = all(s.status in ["dispensed", "cancelled"] for s in subs)
        
    if all_done:
        parent.status = Order.Status.COMPLETED
        parent.save(update_fields=["status"])

@receiver(post_save, sender=LabOrder)
def sync_lab_order(sender, instance, **kwargs):
    _check_and_complete_parent_order(instance)

@receiver(post_save, sender=RadiologyOrder)
def sync_rad_order(sender, instance, **kwargs):
    _check_and_complete_parent_order(instance)

@receiver(post_save, sender=PharmacyOrder)
def sync_pharm_order(sender, instance, **kwargs):
    _check_and_complete_parent_order(instance)
''')

print("==> Patching clinical/apps.py to load signals")
ap = ROOT / "clinical" / "apps.py"
a = ap.read_text(encoding="utf-8")
if "def ready(self):" not in a:
    a = a.replace(
        '    name = "clinical"',
        '    name = "clinical"\n\n    def ready(self):\n        import clinical.signals  # noqa: F401'
    )
    ap.write_text(a, encoding="utf-8")

# ─── 2. BACKEND: Backfill Existing Stuck Orders ────────────────────────
print("==> Backfilling stuck parent orders")
backfill = ROOT / "temp_sync.py"
backfill.write_text('''\
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder
from clinical.signals import _check_and_complete_parent_order
from common.context import db_tenant_context
from tenants.models import Tenant

for t in Tenant.objects.all():
    with db_tenant_context(t):
        pending = Order.all_objects.filter(tenant=t, status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS])
        fixed = 0
        for order in pending:
            if order.kind == "lab":
                subs = LabOrder.all_objects.filter(order=order)
                if subs.exists(): _check_and_complete_parent_order(subs.first())
            elif order.kind == "radiology":
                subs = RadiologyOrder.all_objects.filter(order=order)
                if subs.exists(): _check_and_complete_parent_order(subs.first())
            elif order.kind == "pharmacy":
                subs = PharmacyOrder.all_objects.filter(order=order)
                if subs.exists(): _check_and_complete_parent_order(subs.first())
        print(f"Checked {t.name}: {pending.count()} pending orders.")
''', encoding="utf-8")
sh(PY, "manage.py", "shell", "<", "temp_sync.py", check=False)
backfill.unlink()

# ─── 3. FRONTEND: Update PharmacyDashboard Error Handling ──────────────
print("==> Updating PharmacyDashboard.tsx")
write_frontend("src/pages/PharmacyDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacyDashboard() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-orders"],
    queryFn: async () => {
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
    onError: (error: any) => {
      // Show the exact reason (e.g., "Insufficient stock for PARA500")
      const msg = error.response?.data?.detail || "Failed to dispense medication.";
      alert(`Dispense Failed:\n\n${msg}`);
    }
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

# ─── 4. Build & Push ───────────────────────────────────────────────────
print("\n==> Running local Vite build to verify")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print(f"     {line}")
        sys.exit(1)

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(clinical): auto-sync parent orders and show dispense errors", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")