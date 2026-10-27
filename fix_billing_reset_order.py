#!/usr/bin/env python3
"""
fix_billing_reset_order.py -- regex-based reset order fix + create field migration.
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


# ─── 1. Regex-based reset order fix ────────────────────────────────────
seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

new_block = '''order_of_deletion = [
        # Billing first — Invoice references Visit and Patient with PROTECT
        InsuranceClaim, Payment, InvoiceItem, Invoice,
        PatientInsurance, InsuranceProvider,
        # Clinical + everything else
        StockMovement, Stock,
        PharmacyItem, PharmacyOrder,
        LabResult, LabOrder, RadiologyOrder,
        OrderItem, Order,
        ClinicalNote,
        VitalValue, Vitals, VitalDefinition,
        Visit, Patient,
        LabTest, Medicine,
        TenantSequence,
        TenantSettings,
        AuditLog,
        User,
    ]'''

# Match `order_of_deletion = [ ... ]` (non-greedy, multiline)
pattern = re.compile(r"order_of_deletion\s*=\s*\[.*?\]", re.DOTALL)
new_seed, count = pattern.subn(new_block, seed, count=1)

if count == 1:
    seed_path.write_text(new_seed, encoding="utf-8")
    print(f"   patched {seed_path.relative_to(ROOT)} (reset order)")
else:
    print("   [ERROR] could not find order_of_deletion block — aborting")
    sys.exit(1)

# ─── 2. Create the pending billing migration ───────────────────────────
print("==> makemigrations billing")
sh(PY, "manage.py", "makemigrations", "billing")

# ─── 3. Migrate ────────────────────────────────────────────────────────
print("==> migrate")
sh(PY, "manage.py", "migrate")

# ─── 4. Reseed ─────────────────────────────────────────────────────────
print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

# ─── 5. Sanity check ───────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")