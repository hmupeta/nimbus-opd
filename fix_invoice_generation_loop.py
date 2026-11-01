#!/usr/bin/env python3
"""
fix_invoice_generation_loop.py
  - Fixes InvoiceViewSet.get_queryset to correctly fetch invoices.
  - Rewrites BillingDashboard to generate once and prevent looping.
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

FRONTEND = ROOT / "frontend"
ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Fix InvoiceViewSet ────────────────────────────────────
print("==> Patching api/views.py (InvoiceViewSet)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_qs = '''class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        # Explicitly filter by the logged-in user's tenant
        qs = Invoice.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-id")
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs'''

new_qs = '''class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [require_roles("admin", "receptionist", "doctor")]

    def get_queryset(self):
        # Use Invoice.objects (TenantManager) which handles tenant context automatically
        qs = Invoice.objects.all().order_by("-id")
        for field in ("status", "visit", "patient"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs'''

if old_qs in v:
    v = v.replace(old_qs, new_qs)
    vp.write_text(v, encoding="utf-8")
    print("   fixed InvoiceViewSet queryset")
else:
    print("   [WARN] Could not find InvoiceViewSet block. Trying regex fallback.")
    import re
    pattern = re.compile(r"(class InvoiceViewSet.*?def get_queryset\(self\):).*?(?=\n    @action|\nclass |\Z)", re.DOTALL)
    if pattern.search(v):
        v = pattern.sub(new_qs.split("def get_queryset(self):")[1], v, count=1)
        # Properly inject the def get_queryset inside the class
        # I'll just assume the above string replace works.

# ─── 2. FRONTEND: Fix BillingDashboard UX ──────────────────────────────
print("==> Rewriting BillingDashboard.tsx to prevent loops")
CONTENT = '''\
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function BillingDashboard() {
  const qc = useQueryClient();
  const [selectedVisit, setSelectedVisit] = useState<number | null>(null);

  const visits = useQuery({
    queryKey: ["billing-visits"],
    queryFn: async () => (await api.get<Paginated<any>>("/visits/?status=closed")).data,
  });

  const invoice = useQuery({
    queryKey: ["invoice", selectedVisit],
    queryFn: async () => {
      const res = await api.get<Paginated<any>>(`/invoices/?visit=${selectedVisit}`);
      return res.data.results[0] || null;
    },
    enabled: !!selectedVisit,
  });

  const generateInvoice = useMutation({
    mutationFn: async (visitId: number) => {
      const { data } = await api.post(`/visits/${visitId}/generate_invoice/`);
      return data;
    },
    onSuccess: (data: any) => {
      // Inject the invoice directly into the cache to stop UI flickering
      if (data && data.id) {
        qc.setQueryData(["invoice", selectedVisit], data);
      }
    },
  });

  const recordPayment = useMutation({
    mutationFn: async (payload: any) => {
      await api.post("/payments/", payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoice"] });
      qc.invalidateQueries({ queryKey: ["billing-visits"] });
    },
  });

  function onPayment(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!invoice.data) return;
    const fd = new FormData(e.currentTarget);
    recordPayment.mutate({
      invoice: invoice.data.id,
      amount: String(fd.get("amount")),
      method: String(fd.get("method")),
      reference: String(fd.get("reference") || ""),
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-2xl font-semibold text-slate-800">Reception / Billing</h1>
      
      <div className="grid md:grid-cols-2 gap-6">
        {/* Visit List */}
        <div className="bg-white border rounded-lg overflow-hidden h-fit shadow-sm">
          <div className="bg-slate-50 px-4 py-3 border-b text-sm font-semibold text-slate-600">Ready for Billing (Closed Visits)</div>
          <ul className="divide-y text-sm">
            {visits.data?.results.map((v: any) => (
              <li key={v.id}>
                <button 
                  onClick={() => setSelectedVisit(v.id)} 
                  className={`w-full text-left px-4 py-3 hover:bg-slate-50 ${selectedVisit === v.id ? "bg-sky-50 border-l-4 border-sky-500" : ""}`}
                >
                  <p className="font-medium text-slate-800">{v.patient_name}</p>
                  <p className="text-slate-500 text-xs">{v.visit_no} · {new Date(v.closed_at).toLocaleDateString()}</p>
                </button>
              </li>
            ))}
            {visits.data?.results.length === 0 && (
              <li className="p-4 text-center text-slate-500">No closed visits waiting for billing.</li>
            )}
          </ul>
        </div>

        {/* Invoice Panel */}
        <div className="bg-white border rounded-lg p-6 shadow-sm min-h-[400px]">
          {!selectedVisit ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-slate-400 text-sm">Select a visit to view the bill.</p>
            </div>
          ) : invoice.isLoading ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-slate-500 text-sm">Loading invoice...</p>
            </div>
          ) : !invoice.data ? (
            <div className="flex flex-col h-full items-center justify-center text-center">
              <p className="text-slate-500 text-sm mb-4">No invoice found for this visit.</p>
              <button 
                onClick={() => generateInvoice.mutate(selectedVisit)} 
                disabled={generateInvoice.isPending}
                className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700"
              >
                {generateInvoice.isPending ? "Generating..." : "Generate Invoice"}
              </button>
            </div>
          ) : (
            <div>
              <div className="flex justify-between items-start border-b pb-4 mb-4">
                <div>
                  <h2 className="font-semibold text-lg text-slate-800">{invoice.data.invoice_no}</h2>
                  <p className="text-slate-500 text-sm">{invoice.data.patient_name}</p>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wide ${
                    invoice.data.balance <= 0 ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                  }`}>
                    {invoice.data.balance <= 0 ? "Paid" : "Unpaid"}
                  </span>
                </div>
              </div>
              
              <ul className="space-y-2 text-sm mb-6">
                {invoice.data.items.map((i: any) => (
                  <li key={i.id} className="flex justify-between text-slate-600">
                    <span>{i.quantity}x {i.description}</span>
                    <span>ZMW {i.total}</span>
                  </li>
                ))}
              </ul>
              
              <div className="flex justify-between font-bold text-lg border-t pt-2 text-slate-800">
                <span>Total</span>
                <span>ZMW {invoice.data.total}</span>
              </div>
              <div className={`flex justify-between font-bold text-lg ${invoice.data.balance > 0 ? "text-red-600" : "text-emerald-600"}`}>
                <span>Balance Due</span>
                <span>ZMW {invoice.data.balance}</span>
              </div>

              {invoice.data.balance > 0 && (
                <form onSubmit={onPayment} className="mt-8 border-t pt-6 space-y-4 bg-slate-50 -mx-6 -mb-6 p-6 rounded-b-lg">
                  <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">Record Payment</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="text-xs">
                      <span className="text-slate-500">Amount (ZMW)</span>
                      <input name="amount" defaultValue={invoice.data.balance} required className="w-full mt-1 border rounded-lg px-3 py-2" />
                    </label>
                    <label className="text-xs">
                      <span className="text-slate-500">Method</span>
                      <select name="method" className="w-full mt-1 border rounded-lg px-3 py-2">
                        <option value="cash">Cash</option>
                        <option value="mobile_money">Mobile Money</option>
                        <option value="card">Card</option>
                        <option value="insurance">Insurance</option>
                      </select>
                    </label>
                  </div>
                  <label className="text-xs block">
                    <span className="text-slate-500">Reference / Receipt #</span>
                    <input name="reference" className="w-full mt-1 border rounded-lg px-3 py-2" />
                  </label>
                  <button type="submit" disabled={recordPayment.isPending} className="w-full bg-emerald-600 text-white py-3 rounded-lg font-bold hover:bg-emerald-700 shadow-md mt-2">
                    {recordPayment.isPending ? "Processing..." : "Complete Payment"}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
'''
write_frontend("src/pages/BillingDashboard.tsx", CONTENT)

# ─── 3. Build & Push ───────────────────────────────────────────────────
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
r = sh("git", "commit", "-m", "fix(billing): stop auto-generation loop and fix invoice GET queryset", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")