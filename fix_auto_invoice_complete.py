#!/usr/bin/env python3
"""
fix_auto_invoice_complete.py
  - Overwrites visits/signals.py to dynamically calculate invoice totals
    based on actual Lab, Radiology, and Pharmacy catalog prices.
  - Backfills invoices for any closed visits missing one.
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

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. Rewrite the Signal ─────────────────────────────────────────────
print("==> Rewriting visits/signals.py")
write("visits/signals.py", '''\
from decimal import Decimal
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from common.context import db_tenant_context
from billing.models import Invoice, InvoiceItem
from clinical.models import Order
from .models import Visit

@receiver(pre_save, sender=Visit)
def track_previous_status(sender, instance, **kwargs):
    """Store the old status so we can detect the transition to 'closed'."""
    if instance.pk:
        old = Visit.all_objects.get(pk=instance.pk)
        instance._previous_status = old.status
    else:
        instance._previous_status = None

@receiver(post_save, sender=Visit)
def auto_generate_invoice(sender, instance, created, **kwargs):
    """Generate a complete invoice when a visit transitions to 'closed'."""
    if created or instance.status != Visit.Status.CLOSED:
        return
    
    prev = getattr(instance, "_previous_status", None)
    if prev == Visit.Status.CLOSED:
        return

    # If an invoice already exists (e.g., created manually), don't duplicate it
    if Invoice.all_objects.filter(visit=instance).exists():
        return

    with db_tenant_context(instance.tenant):
        inv = Invoice.objects.create(
            visit=instance,
            patient=instance.patient,
            status=Invoice.Status.DRAFT,
            currency="ZMW",
        )
        
        # 1. Consultation Fee
        InvoiceItem.objects.create(
            invoice=inv,
            category=InvoiceItem.Category.CONSULTATION,
            description="OPD Consultation",
            quantity=1,
            unit_price=Decimal("150.00")
        )

        # 2. Pull from Orders (Lab, Radiology, Pharmacy)
        for order in instance.orders.all():
            for item in order.items.all():
                price = Decimal("0.00")
                
                if order.kind == Order.Kind.LAB:
                    from lab.models import LabTest
                    test = LabTest.all_objects.filter(tenant=instance.tenant, code=item.code).first()
                    if test:
                        price = test.base_price
                
                elif order.kind == Order.Kind.RADIOLOGY:
                    from radiology.models import RadiologyExam
                    exam = RadiologyExam.all_objects.filter(tenant=instance.tenant, code=item.code).first()
                    if exam:
                        price = exam.base_price
                
                elif order.kind == Order.Kind.PHARMACY:
                    from pharmacy.models import Medicine
                    med = Medicine.all_objects.filter(tenant=instance.tenant, code=item.code).first()
                    if med:
                        price = med.base_price

                # Add to invoice
                InvoiceItem.objects.create(
                    invoice=inv,
                    category=order.kind,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=price,
                    order_item_code=item.code
                )
                
        inv.recalculate()
''')

# ─── 2. Backfill Invoices for existing closed visits ───────────────────
print("==> Backfilling invoices for any closed visits missing one")
backfill_script = '''
from tenants.models import Tenant
from common.context import db_tenant_context
from visits.models import Visit
from billing.models import Invoice
from visits.signals import auto_generate_invoice

count = 0
for t in Tenant.objects.all():
    with db_tenant_context(t):
        closed_visits = Visit.all_objects.filter(tenant=t, status=Visit.Status.CLOSED)
        for v in closed_visits:
            if not Invoice.all_objects.filter(visit=v).exists():
                # Trigger the signal logic manually
                auto_generate_invoice(sender=Visit, instance=v, created=False)
                count += 1
print(f"Generated invoices for {count} closed visits.")
'''
r = subprocess.run([str(PY), "manage.py", "shell", "-c", backfill_script], cwd=ROOT, env=ENV, capture_output=True, text=True)
print("   " + r.stdout.strip())
if r.returncode != 0:
    print(r.stderr)

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(billing): dynamically fetch catalog prices when auto-generating invoices", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")