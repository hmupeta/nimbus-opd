#!/usr/bin/env python3
"""
fix_queryset_caching.py -- Fix TenantManager querysets evaluating to empty at startup.
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

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


# ─── 1. Patch api/views.py ─────────────────────────────────────────────
print("==> Patching api/views.py (replacing queryset attributes with get_queryset methods)")
vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Regex to find: "    queryset = Something.objects.all()"
# and replace with a get_queryset method
def replace_queryset(match):
    indent = match.group(1)
    model = match.group(2)
    return f"{indent}def get_queryset(self):\n{indent}    return {model}.objects.all()"

# We only want to replace it if there isn't already a get_queryset defined right below it.
# Since our code structure is simple, we can do a targeted replacement for the known viewsets.
views_to_patch = [
    "TenantSequence", "MobileMoneyConfig", "PaymentGatewayConfig", "SmsConfig",
    "User", "Vitals", "VitalDefinition", "VitalValue", "ClinicalNote",
    "Order", "OrderItem", "LabTest", "LabOrder", "LabResult",
    "RadiologyOrder", "Medicine", "PharmacyOrder", "PharmacyItem", "Stock",
    "StockMovement", "InsuranceProvider", "PatientInsurance", "Invoice",
    "InvoiceItem", "Payment", "InsuranceClaim", "Appointment"
]

for model in views_to_patch:
    old_str = f"    queryset = {model}.objects.all()"
    new_str = f"    def get_queryset(self):\n        return {model}.objects.all()"
    if old_str in v:
        v = v.replace(old_str, new_str)

# Special case for VitalsViewSet which has a perform_create below it
v = v.replace(
    "    def get_queryset(self):\n        return Vitals.objects.all()\n\n    def perform_create(self, serializer):",
    "    def get_queryset(self):\n        return Vitals.objects.all()\n\n    def perform_create(self, serializer):"
)

vp.write_text(v, encoding="utf-8")
print("   patched api/views.py")

# ─── 2. Fix the SmsLog ProtectedError in seed_demo ─────────────────────
print("==> Ensuring SmsLog is wiped before Tenant in reset")
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

if "from notifications.models import SmsLog" not in seed:
    seed = seed.replace(
        "from patients.models import Patient",
        "from patients.models import Patient\nfrom notifications.models import SmsLog"
    )

if "SmsLog," not in seed.split("order_of_deletion")[1].split("]")[0]:
    seed = seed.replace(
        "        TenantSequence,\n        TenantSettings,\n        AuditLog,",
        "        TenantSequence,\n        TenantSettings,\n        SmsLog,\n        AuditLog,"
    )

seed_path.write_text(seed, encoding="utf-8")
print("   patched seed_demo.py")

# ─── 3. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset (NO_REDIS=1)")
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
subprocess.run([str(PY), "manage.py", "seed_demo", "--reset"], check=True, env=seed_env)

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Restart the Django server.")