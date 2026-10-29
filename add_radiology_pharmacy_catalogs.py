#!/usr/bin/env python3
"""
add_radiology_pharmacy_catalogs.py
  - Adds RadiologyExam model + Admin UI.
  - Adds Medicine Admin UI.
  - Allows Doctors to order custom Radiology and Pharmacy items.
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

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")

def write_frontend(rel: str, content: str):
    p = FRONTEND / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote frontend/{rel}")

# ─── 1. BACKEND: Add RadiologyExam Model ───────────────────────────────
print("==> Updating radiology/models.py")
rm = ROOT / "radiology" / "models.py"
r = rm.read_text(encoding="utf-8")
if "class RadiologyExam" not in r:
    r += '''


class RadiologyExam(TenantAwareModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    modality = models.CharField(max_length=8, choices=RadiologyOrder.Modality.choices)
    body_part = models.CharField(max_length=64)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_radexam_code"),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
'''
    rm.write_text(r, encoding="utf-8")

# ─── 2. BACKEND: Serializers & Views ───────────────────────────────────
print("==> Updating api/serializers.py")
sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")
if "class RadiologyExamSerializer" not in s:
    s = s.replace(
        "class RadiologyOrderSerializer(serializers.ModelSerializer):",
        '''class RadiologyExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = RadiologyExam
        fields = ["id", "code", "name", "modality", "body_part", "base_price", "is_active"]
        read_only_fields = ["id"]


class RadiologyOrderSerializer(serializers.ModelSerializer):'''
    )
    # Ensure import
    s = s.replace(
        "from radiology.models import RadiologyOrder",
        "from radiology.models import RadiologyExam, RadiologyOrder"
    )
    sp.write_text(s, encoding="utf-8")

print("==> Updating api/views.py")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Add RadiologyExamViewSet
if "class RadiologyExamViewSet" not in v:
    v = v.replace(
        "class RadiologyOrderViewSet(TenantScopedViewSet):",
        '''class RadiologyExamViewSet(TenantScopedViewSet):
    serializer_class = RadiologyExamSerializer
    queryset = RadiologyExam.objects.all()
    permission_classes = [require_roles("admin", "radiology", "doctor", "nurse")]


class RadiologyOrderViewSet(TenantScopedViewSet):'''
    )
    # Import serializer
    v = v.replace(
        "RadiologyOrderSerializer,",
        "RadiologyExamSerializer, RadiologyOrderSerializer,"
    )

# Update order_radiology to accept custom
if "custom_modality" not in v:
    old_rad = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_radiology(self, request, pk=None):
        visit = self.get_object()
        modality = request.data.get("modality")
        body_part = request.data.get("body_part")
        notes = request.data.get("notes", "")

        if not modality or not body_part:
            return Response({"detail": "modality and body_part are required"}, status=status.HTTP_400_BAD_REQUEST)

        from radiology.models import RadiologyOrder
        
        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.RADIOLOGY, status=Order.Status.PENDING, notes=notes)
            OrderItem.objects.create(order=order, code=f"{modality}-{body_part}", description=f"{modality} {body_part}", quantity=1)
            RadiologyOrder.objects.create(
                visit=visit, order=order, modality=modality, body_part=body_part, status=RadiologyOrder.Status.PENDING
            )

        return Response({"detail": "Radiology ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)'''

    new_rad = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def order_radiology(self, request, pk=None):
        visit = self.get_object()
        exam_id = request.data.get("exam")
        custom_modality = request.data.get("custom_modality")
        custom_body_part = request.data.get("custom_body_part")
        notes = request.data.get("notes", "")

        from radiology.models import RadiologyExam, RadiologyOrder
        from decimal import Decimal

        if exam_id:
            exam = RadiologyExam.objects.filter(id=exam_id).first()
            if not exam:
                return Response({"detail": "Invalid exam"}, status=status.HTTP_400_BAD_REQUEST)
            modality = exam.modality
            body_part = exam.body_part
            code = exam.code
            desc = exam.name
            price = exam.base_price
        elif custom_modality and custom_body_part:
            modality = custom_modality
            body_part = custom_body_part
            code = f"{modality}-{body_part}"
            desc = f"{modality} {body_part}"
            price = Decimal("0.00")
        else:
            return Response({"detail": "exam or custom details are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.RADIOLOGY, status=Order.Status.PENDING, notes=notes)
            OrderItem.objects.create(order=order, code=code, description=desc, quantity=1)
            RadiologyOrder.objects.create(
                visit=visit, order=order, modality=modality, body_part=body_part, status=RadiologyOrder.Status.PENDING
            )
            
            # Update the price of the auto-generated invoice item later
            # (Handled in the invoice generation logic based on the OrderItem code)

        return Response({"detail": "Radiology ordered", "order_id": order.id}, status=status.HTTP_201_CREATED)'''
    v = v.replace(old_rad, new_rad)

# Update prescribe to accept custom medicine
if "custom_medicine_name" not in v:
    old_presc = '''        from pharmacy.models import Medicine, PharmacyOrder, PharmacyItem
        med = Medicine.objects.filter(id=med_id).first()
        if not med:
            return Response({"detail": "Invalid medicine"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.PHARMACY, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=med.code, description=med.name, quantity=qty)
            p_order = PharmacyOrder.objects.create(visit=visit, order=order, status=PharmacyOrder.Status.PENDING)
            PharmacyItem.objects.create(
                pharmacy_order=p_order, medicine=med, dose=dose, frequency=freq,
                duration_days=duration, quantity_prescribed=qty
            )'''
    
    new_presc = '''        from pharmacy.models import Medicine, PharmacyOrder, PharmacyItem
        from decimal import Decimal
        
        custom_med_name = request.data.get("custom_medicine_name")
        
        if med_id:
            med = Medicine.objects.filter(id=med_id).first()
            if not med:
                return Response({"detail": "Invalid medicine"}, status=status.HTTP_400_BAD_REQUEST)
        elif custom_med_name:
            med, _ = Medicine.objects.get_or_create(
                tenant=visit.tenant, name=custom_med_name,
                defaults={"code": custom_med_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )
        else:
            return Response({"detail": "medicine or custom_medicine_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.PHARMACY, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=med.code, description=med.name, quantity=qty)
            p_order = PharmacyOrder.objects.create(visit=visit, order=order, status=PharmacyOrder.Status.PENDING)
            PharmacyItem.objects.create(
                pharmacy_order=p_order, medicine=med, dose=dose, frequency=freq,
                duration_days=duration, quantity_prescribed=qty
            )'''
    v = v.replace(old_presc, new_presc)

# Wire URL for RadiologyExam
if 'router.register("radiology-exams"' not in vp.read_text(encoding="utf-8"):
    up = ROOT / "api" / "urls.py"
    u = up.read_text(encoding="utf-8")
    u = u.replace(
        'from .views import (',
        'from .views import (\n    RadiologyExamViewSet,'
    )
    u = u.replace(
        'router.register("radiology-orders", RadiologyOrderViewSet, basename="rad-order")',
        'router.register("radiology-orders", RadiologyOrderViewSet, basename="rad-order")\n'
        'router.register("radiology-exams", RadiologyExamViewSet, basename="rad-exam")'
    )
    up.write_text(u, encoding="utf-8")

vp.write_text(v, encoding="utf-8")

# ─── 3. RLS Migration for RadiologyExam ────────────────────────────────
print("==> Adding RLS policy for radiology_radiologyexam")
write("common/migrations/0008_rls_rad_exam.py", '''\
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("radiology", "0004_radiologyexam"),
        ("common", "0007_rls_sms"),
    ]
    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "radiology_radiologyexam" ENABLE ROW LEVEL SECURITY;
                ALTER TABLE "radiology_radiologyexam" FORCE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS tenant_isolation ON "radiology_radiologyexam";
                CREATE POLICY tenant_isolation ON "radiology_radiologyexam"
                    USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """,
            reverse_sql="""
                DROP POLICY IF EXISTS tenant_isolation ON "radiology_radiologyexam";
                ALTER TABLE "radiology_radiologyexam" DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
''')

# ─── 4. FRONTEND: Update VisitTimeline Forms ───────────────────────────
print("==> Updating VisitTimeline.tsx")
vt = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"
c = vt.read_text(encoding="utf-8")

# 4a. Add queries for new catalogs
if "const radExams = useQuery" not in c:
    c = c.replace(
        'const meds = useQuery({',
        '''const radExams = useQuery({
    queryKey: ["radiology-exams"],
    queryFn: async () => (await api.get<Paginated<any>>("/radiology-exams/")).data.results,
  });

  const meds = useQuery({'''
    )

# 4b. Update Radiology Form
old_rad_form = '''                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); orderRadiology.mutate({ modality: fd.get("modality"), body_part: fd.get("body_part"), notes: fd.get("notes") }); }} className="space-y-2 bg-orange-50 p-2 rounded border border-orange-100">
                  <div className="grid grid-cols-2 gap-1">
                    <select name="modality" required className="w-full border rounded px-2 py-1 text-xs">
                      <option value="X-ray">X-ray</option>
                      <option value="CT">CT</option>
                      <option value="MRI">MRI</option>
                      <option value="US">Ultrasound</option>
                    </select>
                    <input name="body_part" placeholder="Body Part (e.g. Chest)" required className="w-full border rounded px-2 py-1 text-xs" />
                  </div>
                  <input name="notes" placeholder="Clinical notes..." className="w-full border rounded px-2 py-1 text-xs" />
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => setShowRadForm(false)} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderRadiology.isPending} className="text-[10px] bg-orange-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>'''

new_rad_form = '''                <form onSubmit={(e) => { 
                  e.preventDefault(); 
                  const fd = new FormData(e.currentTarget); 
                  const examVal = fd.get("exam");
                  if (examVal === "custom") {
                    orderRadiology.mutate({ custom_modality: fd.get("custom_modality"), custom_body_part: fd.get("custom_body_part"), notes: fd.get("notes") });
                  } else {
                    orderRadiology.mutate({ exam: Number(examVal), notes: fd.get("notes") });
                  }
                }} className="space-y-2 bg-orange-50 p-2 rounded border border-orange-100">
                  <select name="exam" required onChange={(e) => setCustomRad(e.target.value === "custom")} className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Exam...</option>
                    {radExams.data?.map((r: any) => <option key={r.id} value={r.id}>{r.name} ({r.modality} {r.body_part})</option>)}
                    <option value="custom">+ Custom / Unlisted Exam</option>
                  </select>
                  {customRad && (
                    <div className="grid grid-cols-2 gap-1">
                      <input name="custom_modality" placeholder="Modality (e.g. X-ray)" required className="w-full border rounded px-2 py-1 text-xs" />
                      <input name="custom_body_part" placeholder="Body Part" required className="w-full border rounded px-2 py-1 text-xs" />
                    </div>
                  )}
                  <input name="notes" placeholder="Clinical notes..." className="w-full border rounded px-2 py-1 text-xs" />
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => { setShowRadForm(false); setCustomRad(false); }} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderRadiology.isPending} className="text-[10px] bg-orange-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>'''
c = c.replace(old_rad_form, new_rad_form)

# 4c. Update Prescribe Form
old_med_form = '''                <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); prescribe.mutate({ medicine: Number(fd.get("medicine")), dose: fd.get("dose"), frequency: fd.get("frequency"), duration_days: Number(fd.get("duration_days")), quantity: Number(fd.get("quantity")) }); }} className="space-y-2 bg-emerald-50 p-2 rounded border border-emerald-100">
                  <select name="medicine" required className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Medication...</option>
                    {meds.data?.map((m: any) => <option key={m.id} value={m.id}>{m.name} {m.strength}</option>)}
                  </select>'''

new_med_form = '''                <form onSubmit={(e) => { 
                  e.preventDefault(); 
                  const fd = new FormData(e.currentTarget); 
                  const medVal = fd.get("medicine");
                  const payload: any = {
                    dose: fd.get("dose"), frequency: fd.get("frequency"),
                    duration_days: Number(fd.get("duration_days")), quantity: Number(fd.get("quantity"))
                  };
                  if (medVal === "custom") {
                    payload.custom_medicine_name = fd.get("custom_medicine_name");
                  } else {
                    payload.medicine = Number(medVal);
                  }
                  prescribe.mutate(payload);
                }} className="space-y-2 bg-emerald-50 p-2 rounded border border-emerald-100">
                  <select name="medicine" required onChange={(e) => setCustomMed(e.target.value === "custom")} className="w-full border rounded px-2 py-1 text-xs">
                    <option value="">Select Medication...</option>
                    {meds.data?.map((m: any) => <option key={m.id} value={m.id}>{m.name} {m.strength}</option>)}
                    <option value="custom">+ Custom / Unlisted Medicine</option>
                  </select>
                  {customMed && (
                    <input name="custom_medicine_name" placeholder="Enter medicine name" required className="w-full border rounded px-2 py-1 text-xs" />
                  )}'''
c = c.replace(old_med_form, new_med_form)

# Add state variables for custom toggles
if "const [customRad, setCustomRad]" not in c:
    c = c.replace(
        "const [showRadForm, setShowRadForm] = useState(false);",
        "const [showRadForm, setShowRadForm] = useState(false);\n  const [customRad, setCustomRad] = useState(false);\n  const [customMed, setCustomMed] = useState(false);"
    )
vt.write_text(c, encoding="utf-8")

# ─── 5. FRONTEND: Admin Catalogs (Radiology & Pharmacy) ────────────────
print("==> Creating RadiologyCatalog.tsx and PharmacyCatalog.tsx")
write_frontend("src/pages/RadiologyCatalog.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function RadiologyCatalog() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const exams = useQuery({
    queryKey: ["radiology-exams"],
    queryFn: async () => (await api.get<Paginated<any>>("/radiology-exams/")).data.results,
  });

  const createExam = useMutation({
    mutationFn: async (payload: any) => await api.post("/radiology-exams/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["radiology-exams"] }); setShowForm(false); },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createExam.mutate({
      code: fd.get("code"), name: fd.get("name"), modality: fd.get("modality"),
      body_part: fd.get("body_part"), base_price: Number(fd.get("price")), is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">Radiology Catalog</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ Add Exam</button>
      </div>
      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm"><span>Code</span><input name="code" required placeholder="e.g. CXR-PA" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Name</span><input name="name" required placeholder="Chest X-Ray PA" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Modality</span>
              <select name="modality" required className="mt-1 w-full border rounded-lg px-3 py-2">
                <option value="X-ray">X-ray</option><option value="CT">CT</option><option value="MRI">MRI</option><option value="US">Ultrasound</option>
              </select>
            </label>
            <label className="text-sm"><span>Body Part</span><input name="body_part" required placeholder="Chest" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Price (ZMW)</span><input type="number" step="0.01" name="price" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
          </div>
          <button type="submit" className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700">Save</button>
        </form>
      )}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Code</th><th className="text-left px-4 py-3">Name</th><th className="text-left px-4 py-3">Modality</th><th className="text-left px-4 py-3">Price</th></tr></thead>
          <tbody className="divide-y">
            {exams.data?.map((e: any) => (
              <tr key={e.id}><td className="px-4 py-3 font-mono">{e.code}</td><td className="px-4 py-3">{e.name}</td><td className="px-4 py-3">{e.modality} ({e.body_part})</td><td className="px-4 py-3">ZMW {e.base_price}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

write_frontend("src/pages/PharmacyCatalog.tsx", '''\
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Paginated } from "../api/types";

export default function PharmacyCatalog() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const meds = useQuery({
    queryKey: ["medicines"],
    queryFn: async () => (await api.get<Paginated<any>>("/medicines/")).data.results,
  });

  const createMed = useMutation({
    mutationFn: async (payload: any) => await api.post("/medicines/", payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medicines"] }); setShowForm(false); },
  });

  function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    createMed.mutate({
      code: fd.get("code"), name: fd.get("name"), form: fd.get("form"), strength: fd.get("strength"),
      base_price: Number(fd.get("price")), is_active: true,
    });
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-800">Pharmacy Catalog</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700">+ Add Medicine</button>
      </div>
      {showForm && (
        <form onSubmit={onCreate} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <label className="text-sm"><span>Code</span><input name="code" required placeholder="e.g. PARA500" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Name</span><input name="name" required placeholder="Paracetamol" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Form</span><input name="form" placeholder="Tablet" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Strength</span><input name="strength" placeholder="500 mg" className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
            <label className="text-sm"><span>Price (ZMW)</span><input type="number" step="0.01" name="price" required className="mt-1 w-full border rounded-lg px-3 py-2" /></label>
          </div>
          <button type="submit" className="bg-sky-600 text-white px-4 py-2 rounded-lg hover:bg-sky-700">Save</button>
        </form>
      )}
      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="text-left px-4 py-3">Code</th><th className="text-left px-4 py-3">Name</th><th className="text-left px-4 py-3">Form</th><th className="text-left px-4 py-3">Price</th></tr></thead>
          <tbody className="divide-y">
            {meds.data?.map((m: any) => (
              <tr key={m.id}><td className="px-4 py-3 font-mono">{m.code}</td><td className="px-4 py-3">{m.name}</td><td className="px-4 py-3">{m.form} {m.strength}</td><td className="px-4 py-3">ZMW {m.base_price}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
''')

# ─── 6. FRONTEND: Navigation & Router ──────────────────────────────────
print("==> Updating Layout and Router")
lp = FRONTEND / "src" / "components" / "Layout.tsx"
l = lp.read_text(encoding="utf-8")
if "Radiology Catalog" not in l:
    l = l.replace(
        '<NavLink to="/lab-catalog" className={linkClass}>Lab Catalog</NavLink>',
        '<NavLink to="/lab-catalog" className={linkClass}>Lab Catalog</NavLink>\n                <NavLink to="/radiology-catalog" className={linkClass}>Radiology Catalog</NavLink>\n                <NavLink to="/pharmacy-catalog" className={linkClass}>Pharmacy Catalog</NavLink>'
    )
    lp.write_text(l, encoding="utf-8")

ap = FRONTEND / "src" / "App.tsx"
app = ap.read_text(encoding="utf-8")
if "RadiologyCatalog" not in app:
    app = app.replace(
        'import LabCatalog from "./pages/LabCatalog";',
        'import LabCatalog from "./pages/LabCatalog";\nimport RadiologyCatalog from "./pages/RadiologyCatalog";\nimport PharmacyCatalog from "./pages/PharmacyCatalog";'
    )
    app = app.replace(
        '<Route path="/lab-catalog" element={<LabCatalog />} />',
        '<Route path="/lab-catalog" element={<LabCatalog />} />\n          <Route path="/radiology-catalog" element={<RadiologyCatalog />} />\n          <Route path="/pharmacy-catalog" element={<PharmacyCatalog />} />'
    )
    ap.write_text(app, encoding="utf-8")

# ─── 7. Migrate & Deploy ───────────────────────────────────────────────
print("==> Running migrations")
sh(PY, "manage.py", "makemigrations", "radiology")
sh(PY, "manage.py", "migrate")

print("==> Done. Push to GitHub and redeploy both services.")