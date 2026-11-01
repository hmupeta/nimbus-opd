#!/usr/bin/env python3
"""
add_self_healing_fix.py
  - Creates a `fix_stuck_orders` management command.
  - Adds it to render.yaml's startCommand so it runs on every deploy.
  - Pushes so the next Render deploy self-heals production.
"""
from __future__ import annotations
import os
import re
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

# ─── 1. Create the management command ──────────────────────────────────
print("==> Creating fix_stuck_orders command")
write("clinical/management/__init__.py", "")
write("clinical/management/commands/__init__.py", "")

write("clinical/management/commands/fix_stuck_orders.py", '''\
from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder, LabResult
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder


class Command(BaseCommand):
    help = "Auto-complete any parent Order whose sub-orders are already done."

    def handle(self, *args, **opts):
        total_fixed = 0

        for tenant in Tenant.objects.all():
            # Bypass RLS: we are running as a maintenance task
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    [str(tenant.id)],
                )

            pending = Order.all_objects.filter(
                tenant=tenant,
                status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS],
            )

            for order in pending:
                should_complete = False

                if order.kind == Order.Kind.LAB:
                    subs = LabOrder.all_objects.filter(order=order)
                    if subs.exists() and all(
                        s.status in ["completed", "cancelled"] for s in subs
                    ):
                        should_complete = True

                elif order.kind == Order.Kind.RADIOLOGY:
                    subs = RadiologyOrder.all_objects.filter(order=order)
                    if subs.exists() and all(
                        s.status in ["reported", "cancelled"] for s in subs
                    ):
                        should_complete = True

                elif order.kind == Order.Kind.PHARMACY:
                    subs = PharmacyOrder.all_objects.filter(order=order)
                    if subs.exists() and all(
                        s.status in ["dispensed", "cancelled"] for s in subs
                    ):
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

# ─── 2. Add to render.yaml startCommand ────────────────────────────────
print("==> Updating render.yaml startCommand")
ry = ROOT / "render.yaml"
if not ry.exists():
    sys.exit("render.yaml not found in repo root")

y = ry.read_text(encoding="utf-8")

# We want: migrate && fix_stuck_orders && seed_demo && gunicorn
old_cmd = "python manage.py migrate --noinput && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
new_cmd = "python manage.py migrate --noinput && python manage.py fix_stuck_orders && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"

if old_cmd in y:
    y = y.replace(old_cmd, new_cmd)
    ry.write_text(y, encoding="utf-8")
    print("   added fix_stuck_orders to startCommand")
elif new_cmd in y:
    print("   startCommand already has fix_stuck_orders")
else:
    print("   [WARN] Could not find the exact startCommand string.")
    print("   Please open render.yaml and change the startCommand to:")
    print(f'   startCommand: "{new_cmd}"')

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")
r = sh("git", "commit", "-m",
       "feat(ops): auto-heal stuck orders on every Render deploy",
       check=False)
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip(): print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  1. nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("  2. Watch the logs. You should see:")
print("       fix_stuck_orders: N order(s) completed.")
print("  3. Then refresh the visit page in the browser — Lab will be green.")