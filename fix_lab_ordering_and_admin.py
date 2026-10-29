#!/usr/bin/env python3
"""
fix_lab_ordering_and_admin.py
  - Allows doctors to read the LabTest catalog.
  - Allows doctors to order a custom (unlisted) lab test.
  - Creates a "Lab Catalog" UI for Clinic Admins to manage tests.
"""
from __future__ import annotations
import os
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

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")
FRONTEND = ROOT / "frontend"

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Fix Permissions & Add Custom Test Logic ───────────────
print("==> Patching api/views.py")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# 1a. Allow doctors/nurses to read the LabTest catalog
v = v.replace(
    'class LabTestViewSet(TenantScopedViewSet):\n    serializer_class = LabTestSerializer\n    queryset = LabTest.objects.all()\n    permission_classes = [require_roles("admin", "lab")]',
    'class LabTestViewSet(TenantScopedViewSet):\n    serializer_class = LabTestSerializer\n    queryset = LabTest.objects.all()\n    permission_classes = [require_roles("admin", "lab", "doctor", "nurse")]'
)

# 1b. Update order_lab to accept custom_test_name
old_order_lab = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_lab(self, request, pk=None):
        visit = self.get_object()
        test_id = request.data.get("test")
        if not test_id:
            return Response({"detail": "test is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        from lab.models import LabTest, LabOrder
        test = LabTest.objects.filter(id=test_id).first()
        if not test:
            return Response({"detail": "Invalid test"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.LAB, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=test.code, description=test.name, quantity=1)
            LabOrder.objects.create(visit=visit, order=order, test=test, status=LabOrder.Status.PENDING)

        return Response({"detail": "Lab ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)'''

new_order_lab = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_lab(self, request, pk=None):
        visit = self.get_object()
        test_id = request.data.get("test")
        custom_test_name = request.data.get("custom_test_name")

        if not test_id and not custom_test_name:
            return Response({"detail": "test or custom_test_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        from lab.models import LabTest, LabOrder
        from decimal import Decimal

        if test_id:
            test = LabTest.objects.filter(id=test_id).first()
            if not test:
                return Response({"detail": "Invalid test"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Create a custom test on the fly so it exists in the DB for the lab tech
            test, _ = LabTest.objects.get_or_create(
                tenant=visit.tenant,
                name=custom_test_name,
                defaults={"code": custom_test_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.LAB, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=test.code, description=test.name, quantity=1)
            LabOrder.objects.create(visit=visit, order=order, test=test, status=LabOrder.Status.PENDING)

        return Response({"detail": "Lab ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)'''

v = v.replace(old_order_lab, new_order_lab)
vp.write_text(v, encoding="utf-8")
print("   patched backend permissions and order logic")

# ─── 2. FRONTEND: Update VisitTimeline Dropdown ────────────────────────
print("==> Updating VisitTimeline.tsx")
vt = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
c = vt.read_text(encoding="utf-8")

# 2a. Add custom test state
if "const [customTest, setCustomTest] = useState(false);" not in c:
    c = c.replace(
        "const [showLabForm, setShowLabForm] = useState(false);",
        "const [showLabForm, setShowLabForm] = useState(false);\n  const [customTest, setCustomTest] = useState(false);"
    )

# 2b. Update the mutation to accept the payload object
old_order_lab_mut = '''  const orderLab = useMutation({
    mutationFn: async (testId: number) => {
      await api.post(`/visits/${id}/order_lab/`, { test: testId });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowLabForm(false);
    },
  });'''

new_order_lab_mut = '''  const orderLab = useMutation({
    mutationFn: async (payload: any) => {
      await api.post(`/visits/${id}/order_lab/`, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["visit", id, "timeline"] });
      setShowLabForm(false);
      setCustomTest(false);
    },
  });'''

if old_order_lab_mut in c:
    c = c.replace(old_order_lab_mut, new_order_lab_mut)

# 2c. Update the UI form
old_lab_form = '''                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); orderLab.mutate(Number(fd.get("test"))); }} className="space-y-2 bg-indigo-50 p-2 rounded border border-indigo-100">
                  <select name="test" required className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Lab Test...</option>
                    {labs.data?.map((l: any) => <option key={l.id} value={l.id}>{l.name} ({l.code})</option>)}
                  </select>
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setShowLabForm(false)} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderLab.isPending} className="text-[10px] bg-indigo-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>'''

new_lab_form = '''                <form onSubmit={(e) => { 
                  e.preventDefault(); 
                  const fd = new FormData(e.currentTarget); 
                  const testVal = fd.get("test");
                  if (testVal === "custom") {
                    orderLab.mutate({ custom_test_name: fd.get("custom_test_name") });
                  } else {
                    orderLab.mutate({ test: Number(testVal) });
                  }
                }} className="space-y-2 bg-indigo-50 p-2 rounded border border-indigo-100">
                  <select name="test" required onChange={(e) => setCustomTest(e.target.value === "custom")} className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Lab Test...</option>
                    {labs.data?.map((l: any) => <option key={l.id} value={l.id}>{l.name} ({l.code})</option>)}
                    <option value="custom">+ Custom / Unlisted Test</option>
                  </select>
                  {customTest && (
                    <input name="custom_test_name" required placeholder="Enter test name (e.g., Malaria RDT)" className="w-full border rounded px-2 py-1 text-xs" />
                  )}
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => { setShowLabForm(false); setCustomTest(false); }} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderLab.isPending} className="text-[10px] bg-indigo-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>'''

if old_lab_form in c:
    c = c.replace(old_lab_form, new_lab_form)
    vt.write_text(c, encoding="utf-8")
    print("   patched VisitTimeline dropdown and custom input")

# ─── 3. FRONTEND: Create Lab Catalog Admin UI ──────────────────────────
print("==> Creating LabCatalog.tsx")
write_frontend("src/pages/LabCatalog.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function LabCatalog() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const tests = useQuery({
    queryKey: ["lab-tests"],
    queryFn: async () => (await api.get<Paginated<any>>("/lab-tests/")).data.results,
  });

  const createTest = useMutation({
    mutationFn: async (payload: any) => await api.post("/lab-tests/", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lab-tests"] });
      setShowForm(false);
    },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createTest.mutate({
      code: fd.get("code"),
      name: fd.get("name"),
      base_price: Number(fd.get("price")),
      specimen_type: fd.get("specimen"),
      is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Lab Test Catalog</h1>
          <p className="text-sm text-slate-500 mt-1">Manage the tests available in the Doctor's dropdown.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 font-medium">
          + Add Lab Test
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm"><span className="text-slate-600">Test Code</span><input name="code" required placeholder="e.g. MAL" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span className="text-slate-600">Test Name</span><input name="name" required placeholder="e.g. Malaria RDT" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span className="text-slate-600">Price (ZMW)</span><input type="number" step="0.01" name="price" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span className="text-slate-600">Specimen</span><input name="specimen" placeholder="e.g. blood" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border rounded-lg hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={createTest.isPending} className="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700">Save Test</button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-3">Code</th>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Price</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tests.data?.map((t: any) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono">{t.code}</td>
                <td className="px-4 py-3 font-medium">{t.name}</td>
                <td className="px-4 py-3">ZMW {t.base_price}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-1 rounded ${t.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {t.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
            {tests.data?.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No lab tests configured yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

# ─── 4. FRONTEND: Navigation & Routing ─────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Lab Catalog" not in l:
    l = l.replace(
        '<NavLink to="/staff" className={linkClass}>Staff</NavLink>',
        '<NavLink to="/staff" className={linkClass}>Staff</NavLink>\n                <NavLink to="/lab-catalog" className={linkClass}>Lab Catalog</NavLink>'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
app = ap.read_text(encoding="utf-8")
if "LabCatalog" not in app:
    app = app.replace(
        'import Staff from "./pages/Staff";',
        'import Staff from "./pages/Staff";\nimport LabCatalog from "./pages/LabCatalog";'
    )
    app = app.replace(
        '<Route path="/staff" element={<Staff />} />',
        '<Route path="/staff" element={<Staff />} />\n          <Route path="/lab-catalog" element={<LabCatalog />} />'
    )
    ap.write_text(app, encoding="utf-8")

print("==> Done. Push to GitHub and redeploy both services.")