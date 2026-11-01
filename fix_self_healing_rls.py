#!/usr/bin/env python3
"""
fix_self_healing_rls.py
  - Fixes the fix_stuck_orders command to use db_tenant_context (which handles RLS correctly).
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT, capture_output=True, text=True)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip(), encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. Rewrite the management command with correct RLS context ────────
print("==> Fixing clinical/management/commands/fix_stuck_orders.py")
write("clinical/management/commands/fix_stuck_orders.py", '''\
from django.core.management.base import BaseCommand
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder
from common.context import db_tenant_context


class Command(BaseCommand):
    help = "Auto-complete any parent Order whose sub-orders are already done."

    def handle(self, *args, **opts):
        total_fixed = 0

        for tenant in Tenant.objects.all():
            # Use the proper context manager so RLS lets us see the orders
            with db_tenant_context(tenant):
                pending = Order.all_objects.filter(
                    tenant=tenant,
                    status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS],
                )

                for order in pending:
                    should_complete = False

                    if order.kind == Order.Kind.LAB:
                        subs = LabOrder.all_objects.filter(order=order)
                        if subs.exists() and all(s.status in ["completed", "cancelled"] for s in subs):
                            should_complete = True

                    elif order.kind == Order.Kind.RADIOLOGY:
                        subs = RadiologyOrder.all_objects.filter(order=order)
                        if subs.exists() and all(s.status in ["reported", "cancelled"] for s in subs):
                            should_complete = True

                    elif order.kind == Order.Kind.PHARMACY:
                        subs = PharmacyOrder.all_objects.filter(order=order)
                        if subs.exists() and all(s.status in ["dispensed", "cancelled"] for s in subs):
                            should_complete = True

                    if should_complete:
                        order.status = Order.Status.COMPLETED
                        order.save(update_fields=["status"])
                        total_fixed += 1
                        self.stdout.write(
                            f"  [FIXED] {tenant.code}: Order #{order.id} ({order.kind})"
                        )

        self.stdout.write(self.style.SUCCESS(
            f"fix_stuck_orders: {total_fixed} order(s) completed."))
''')

# ─── 2. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(ops): use db_tenant_context in fix_stuck_orders to bypass RLS correctly", check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. Watch the logs. It will now find the stuck orders and fix them.")