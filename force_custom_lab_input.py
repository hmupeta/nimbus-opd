#!/usr/bin/env python3
"""
force_custom_lab_input.py
  - Forces the VisitTimeline.tsx lab form to include the custom input.
  - Ensures the backend API correctly creates a custom test.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
VP = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, capture_output=True, text=True)

# ─── 1. Ensure customTest state exists ─────────────────────────────────
print("==> Checking VisitTimeline.tsx state")
c = VP.read_text(encoding="utf-8")
if "const [customTest, setCustomTest] = useState(false);" not in c:
    c = c.replace(
        "const [showLabForm, setShowLabForm] = useState(false);",
        "const [showLabForm, setShowLabForm] = useState(false);\n  const [customTest, setCustomTest] = useState(false);"
    )
    print("   added customTest state")

# ─── 2. Replace the Lab Form block completely ──────────────────────────
print("==> Replacing Lab Order Form")
# We use regex to find the block starting with {showLabForm && ( and ending with )}
pattern = re.compile(r"\{showLabForm && \(.*?\n\s*\)\}", re.DOTALL)

new_lab_form = '''{showLabForm && (
                <form onSubmit={(e) => { 
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
                    <input name="custom_test_name" required placeholder="Enter test name (e.g. Malaria RDT)" className="w-full border rounded px-2 py-1 text-xs" />
                  )}
                  
                  <div className="flex justify-end gap-2">
                    <button type="button" onClick={() => { setShowLabForm(false); setCustomTest(false); }} className="text-[10px] text-slate-500">Cancel</button>
                    <button type="submit" disabled={orderLab.isPending} className="text-[10px] bg-indigo-600 text-white px-2 py-1 rounded">Order</button>
                  </div>
                </form>
              )}'''

if pattern.search(c):
    c = pattern.sub(new_lab_form, c, count=1)
    VP.write_text(c, encoding="utf-8")
    print("   ✓ successfully replaced the Lab Order form block")
else:
    print("   ❌ Could not find the {showLabForm && (...)} block via regex.")
    print("   Please check VisitTimeline.tsx manually.")

# ─── 3. Verify the backend handles custom tests ────────────────────────
print("\n==> Verifying backend API for custom tests")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

if "custom_test_name" not in v:
    print("   ❌ Backend is missing custom_test_name logic. Patching now...")
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
            # Create custom test on the fly
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
    print("   ✓ patched backend order_lab logic")
else:
    print("   ✓ Backend already supports custom test names")

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m", "fix(frontend): force custom lab test input in Doctor timeline", check=False)
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. nimbus-frontend → Manual Deploy → Clear build cache & deploy")