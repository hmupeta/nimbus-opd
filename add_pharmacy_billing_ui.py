#!/usr/bin/env python3
"""
add_pharmacy_billing_ui.py -- Add Pharmacy Queue and Receptionist Billing UI.
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

# ─── 1. BACKEND: Add generate_invoice to VisitViewSet ──────────────────
print("==> Patching api/views.py (Adding generate_invoice action)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "def generate_invoice(self, request, pk=None):" not in v:
    invoice_action = '''
    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "receptionist")])
    def generate_invoice(self, request, pk=None):
        visit = self.get_object()
        if Invoice.all_objects.filter(visit=visit).exists():
            inv = Invoice.all_objects.get(visit=visit)
            return Response({"detail": "Invoice already exists", "invoice_id": inv.id})

        from billing.models import Invoice, InvoiceItem
        from decimal import Decimal
        
        with transaction.atomic():
            inv = Invoice.objects.create(
                visit=visit, patient=visit.patient, status=Invoice.Status.ISSUED, currency="ZMW"
            )
            # Consultation fee
            InvoiceItem.objects.create(
                invoice=inv, category=InvoiceItem.Category.CONSULTATION,
                description="OPD Consultation", quantity=1, unit_price=Decimal("150.00")
            )
            # Orders
            for order in visit.orders.all():
                for item in order.items.all():
                    price = Decimal("0.00")
                    if order.kind == "lab":
                        from lab.models import LabTest
                        t = LabTest.objects.filter(code=item.code).first()
                        price = t.base_price if t else Decimal("0.00")
                    elif order.kind == "pharmacy":
                        from pharmacy.models import Medicine
                        m = Medicine.objects.filter(code=item.code).first()
                        price = m.base_price if m else Decimal("0.00")
                    elif order.kind == "radiology":
                        price = Decimal("120.00")
                    
                    if price > 0:
                        InvoiceItem.objects.create(
                            invoice=inv, category=order.kind,
                            description=item.description, quantity=item.quantity,
                            unit_price=price, order_item_code=item.code
                        )
            inv.recalculate()
            
        return Response({"detail": "Invoice generated", "invoice_id": inv.id})

'''
    v = v.replace("class VitalsViewSet(TenantScopedViewSet):", invoice_action + "\nclass VitalsViewSet(TenantScopedViewSet):")
    vp.write_text(v, encoding="utf-8")

# Ensure imports in views.py
if "from billing.models import Invoice" not in v:
    v = v.replace("from billing.models import (", "from billing.models import Invoice, InvoiceItem, Payment, InsuranceClaim, InsuranceProvider, PatientInsurance, (\n    ")
    vp.write_text(v, encoding="utf-8")

# ─── 2. FRONTEND: Pharmacy Dashboard ───────────────────────────────────
print("==> Creating Pharmacy Dashboard")
write_frontend("src/pages/PharmacyDashboard.tsx", '''\
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacyDashboard() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-orders", "pending"],
    queryFn: async () =>
      (await api.get<Paginated<any>>("/pharmacy-orders/?status=pending")).data,
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
              <th className="text-left px-4 py-3">Medications</th>
              <th className="text-left px-4 py-3">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {data?.results.map((o: any) => (
              <tr key={o.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{o.visit_no || "Visit"}</td>
                <td className="px-4 py-3">
                  <ul className="text-xs space-y-1">
                    {o.items.map((i: any) => (
                      <li key={i.id}>{i.quantity_prescribed}x {i.medicine_name} ({i.dose} {i.frequency})</li>
                    ))}
                  </ul>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">{o.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => dispense.mutate(o.id)}
                    disabled={dispense.isPending}
                    className="rounded bg-sky-600 text-white text-xs px-3 py-1.5 hover:bg-sky-700 disabled:opacity-50"
                  >
                    Dispense
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.results.length === 0 && <p className="p-6 text-center text-slate-500">No pending prescriptions.</p>}
      </div>
    </div>
  );
}
''')

# Fix PharmacyOrderSerializer to include medicine names & visit_no
sp = ROOT / "api" / "billing_serializers.py"
# Actually PharmacyOrder is in api/serializers.py
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")
if "medicine_name" not in s:
    old_pharm_item = '''class PharmacyItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyItem
        fields = ["id", "pharmacy_order", "medicine", "dose", "frequency",
                  "duration_days", "route", "quantity_prescribed",
                  "quantity_dispensed", "batch_no", "expiry_date"]
        read_only_fields = ["id"]'''
    new_pharm_item = '''class PharmacyItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    class Meta:
        model = PharmacyItem
        fields = ["id", "pharmacy_order", "medicine", "medicine_name", "dose", "frequency",
                  "duration_days", "route", "quantity_prescribed",
                  "quantity_dispensed", "batch_no", "expiry_date"]
        read_only_fields = ["id"]'''
    s = s.replace(old_pharm_item, new_pharm_item)
    
    old_pharm_order = '''class PharmacyOrderSerializer(serializers.ModelSerializer):
    items = PharmacyItemSerializer(many=True, read_only=True)

    class Meta:
        model = PharmacyOrder
        fields = ["id", "visit", "order", "status", "dispensed_by",
                  "dispensed_at", "notes", "items"]
        read_only_fields = ["id", "dispensed_by", "dispensed_at"]'''
    new_pharm_order = '''class PharmacyOrderSerializer(serializers.ModelSerializer):
    items = PharmacyItemSerializer(many=True, read_only=True)
    visit_no = serializers.CharField(source="visit.visit_no", read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)

    class Meta:
        model = PharmacyOrder
        fields = ["id", "visit", "visit_no", "patient_name", "order", "status", "dispensed_by",
                  "dispensed_at", "notes", "items"]
        read_only_fields = ["id", "dispensed_by", "dispensed_at"]'''
    s = s.replace(old_pharm_order, new_pharm_order)
    sp.write_text(s, encoding="utf-8")

# ─── 3. FRONTEND: Billing Dashboard ────────────────────────────────────
print("==> Creating Billing Dashboard")
write_frontend("src/pages/BillingDashboard.tsx", '''\
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoice"] }),
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
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Reception / Billing</h1>
      
      <div className="grid md:grid-cols-2 gap-6">
        {/* Visit List */}
        <div className="bg-white border rounded-lg overflow-hidden h-fit">
          <div className="bg-slate-50 px-4 py-2 border-b text-sm font-semibold text-slate-600">Ready for Billing (Closed Visits)</div>
          <ul className="divide-y text-sm">
            {visits.data?.results.map((v: any) => (
              <li key={v.id}>
                <button onClick={() => setSelectedVisit(v.id)} className={`w-full text-left px-4 py-3 hover:bg-slate-50 ${selectedVisit === v.id ? "bg-sky-50" : ""}`}>
                  <p className="font-medium text-slate-800">{v.patient_name}</p>
                  <p className="text-slate-500 text-xs">{v.visit_no} · {new Date(v.closed_at).toLocaleDateString()}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Invoice Panel */}
        <div className="bg-white border rounded-lg p-6">
          {!selectedVisit ? (
            <p className="text-slate-500 text-sm">Select a visit to view or generate the bill.</p>
          ) : invoice.isLoading ? (
            <p className="text-slate-500 text-sm">Checking for invoice…</p>
          ) : !invoice.data ? (
            <div className="text-center py-8">
              <p className="text-slate-500 text-sm mb-4">No invoice generated yet.</p>
              <button onClick={() => generateInvoice.mutate(selectedVisit)} disabled={generateInvoice.isPending} className="bg-sky-600 text-white px-4 py-2 rounded text-sm hover:bg-sky-700">
                Generate Invoice
              </button>
            </div>
          ) : (
            <div>
              <div className="flex justify-between items-start border-b pb-4 mb-4">
                <div>
                  <h2 className="font-semibold text-lg">{invoice.data.invoice_no}</h2>
                  <p className="text-slate-500 text-sm">{invoice.data.patient_name}</p>
                </div>
                <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded font-medium">{invoice.data.status}</span>
              </div>
              
              <ul className="space-y-2 text-sm mb-4">
                {invoice.data.items.map((i: any) => (
                  <li key={i.id} className="flex justify-between text-slate-600">
                    <span>{i.quantity}x {i.description}</span>
                    <span>ZMW {i.total}</span>
                  </li>
                ))}
              </ul>
              
              <div className="flex justify-between font-bold text-lg border-t pt-2">
                <span>Total</span>
                <span>ZMW {invoice.data.total}</span>
              </div>
              <div className="flex justify-between font-medium text-emerald-600">
                <span>Balance Due</span>
                <span>ZMW {invoice.data.balance}</span>
              </div>

              {invoice.data.balance > 0 && (
                <form onSubmit={onPayment} className="mt-6 border-t pt-4 space-y-3 bg-slate-50 -mx-6 -mb-6 p-6 rounded-b-lg">
                  <h3 className="text-sm font-semibold text-slate-700">Record Payment</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="text-xs">
                      <span className="text-slate-500">Amount</span>
                      <input name="amount" defaultValue={invoice.data.balance} required className="w-full mt-1 border rounded px-2 py-1.5" />
                    </label>
                    <label className="text-xs">
                      <span className="text-slate-500">Method</span>
                      <select name="method" className="w-full mt-1 border rounded px-2 py-1.5">
                        <option value="cash">Cash</option>
                        <option value="mobile_money">Mobile Money</option>
                        <option value="insurance">Insurance</option>
                      </select>
                    </label>
                  </div>
                  <label className="text-xs block">
                    <span className="text-slate-500">Reference / Receipt #</span>
                    <input name="reference" className="w-full mt-1 border rounded px-2 py-1.5" />
                  </label>
                  <button type="submit" disabled={recordPayment.isPending} className="w-full bg-emerald-600 text-white py-2 rounded text-sm font-medium hover:bg-emerald-700">
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
''')

# ─── 4. FRONTEND: Update Navigation & Routing ──────────────────────────
print("==> Updating Navigation and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Pharmacy Queue" not in l:
    l = l.replace(
        '{user?.role === "lab" || user?.role === "admin" ? (\n              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>\n            ) : null}',
        '''{user?.role === "lab" || user?.role === "admin" ? (
              <NavLink to="/lab" className={linkClass}>Lab Queue</NavLink>
            ) : null}
            {user?.role === "pharmacist" || user?.role === "admin" ? (
              <NavLink to="/pharmacy" className={linkClass}>Pharmacy</NavLink>
            ) : null}
            {user?.role === "receptionist" || user?.role === "admin" ? (
              <NavLink to="/billing" className={linkClass}>Billing</NavLink>
            ) : null}'''
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
a = ap.read_text(encoding="utf-8")
if "PharmacyDashboard" not in a:
    a = a.replace(
        'import LabDashboard from "./pages/LabDashboard";',
        'import LabDashboard from "./pages/LabDashboard";\nimport PharmacyDashboard from "./pages/PharmacyDashboard";\nimport BillingDashboard from "./pages/BillingDashboard";'
    )
    a = a.replace(
        '<Route path="/lab" element={<LabDashboard />} />',
        '<Route path="/lab" element={<LabDashboard />} />\n          <Route path="/pharmacy" element={<PharmacyDashboard />} />\n          <Route path="/billing" element={<BillingDashboard />} />'
    )
    ap.write_text(a, encoding="utf-8")

# ─── 5. Ensure Admin works for these roles ─────────────────────────────
# Add role mapping in auth.ts if missing (no need, backend handles it)

print("==> Done. You must restart the Django server.")