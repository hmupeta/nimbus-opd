#!/usr/bin/env python3
"""
fix_prescribe_endpoint.py
  - Fixes the backend `prescribe` method to accept either a standard medicine ID or a custom name.
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

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, env=ENV, capture_output=True, text=True)

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

old_prescribe = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def prescribe(self, request, pk=None):
        visit = self.get_object()
        med_id = request.data.get("medicine")
        dose = request.data.get("dose", "1 tab")
        freq = request.data.get("frequency", "OD")
        duration = request.data.get("duration_days", 1)
        qty = request.data.get("quantity", 1)

        if not med_id:
            return Response({"detail": "medicine is required"}, status=status.HTTP_400_BAD_REQUEST)

        from pharmacy.models import Medicine, PharmacyOrder, PharmacyItem
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
            )

        return Response({"detail": "Prescription added", "order_id": order.id}, status=status.HTTP_201_CREATED)'''

new_prescribe = '''    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "doctor")])
    def prescribe(self, request, pk=None):
        visit = self.get_object()
        med_id = request.data.get("medicine")
        custom_med_name = request.data.get("custom_medicine_name")
        
        dose = request.data.get("dose", "1 tab")
        freq = request.data.get("frequency", "OD")
        duration = request.data.get("duration_days", 1)
        qty = request.data.get("quantity", 1)

        if not med_id and not custom_med_name:
            return Response({"detail": "medicine or custom_medicine_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        from pharmacy.models import Medicine, PharmacyOrder, PharmacyItem
        from decimal import Decimal
        
        if med_id:
            med = Medicine.objects.filter(id=med_id).first()
            if not med:
                return Response({"detail": "Invalid medicine"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            med, _ = Medicine.objects.get_or_create(
                tenant=visit.tenant, name=custom_med_name,
                defaults={"code": custom_med_name[:10].upper().replace(" ", ""), "base_price": Decimal("0.00")}
            )

        with transaction.atomic():
            order = Order.objects.create(visit=visit, ordered_by=request.user, kind=Order.Kind.PHARMACY, status=Order.Status.PENDING)
            OrderItem.objects.create(order=order, code=med.code, description=med.name, quantity=qty)
            p_order = PharmacyOrder.objects.create(visit=visit, order=order, status=PharmacyOrder.Status.PENDING)
            PharmacyItem.objects.create(
                pharmacy_order=p_order, medicine=med, dose=dose, frequency=freq,
                duration_days=duration, quantity_prescribed=qty
            )

        return Response({"detail": "Prescription added", "order_id": order.id}, status=status.HTTP_201_CREATED)'''

if old_prescribe in v:
    v = v.replace(old_prescribe, new_prescribe)
    vp.write_text(v, encoding="utf-8")
    print("   patched api/views.py (fixed prescribe logic)")
else:
    print("   [WARN] Could not find the exact prescribe block. Checking for custom_medicine_name...")
    if "custom_medicine_name" in v:
        print("   Looks like it might already be patched, but proceeding with a backup replacement.")
        # Just try to replace the bad check
        v = v.replace(
            '        if not med_id:\n            return Response({"detail": "medicine is required"}, status=status.HTTP_400_BAD_REQUEST)',
            '        if not med_id and not custom_med_name:\n            return Response({"detail": "medicine or custom_medicine_name is required"}, status=status.HTTP_400_BAD_REQUEST)'
        )
        vp.write_text(v, encoding="utf-8")

print("\n==> manage.py check")
sh(PY, "manage.py", "check")

print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(api): allow prescribing custom medicines without a catalog ID", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")