#!/usr/bin/env python3
"""
fix_seed_smslog.py -- add SmsLog to the reset deletion order, then reseed.
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


def sh(*cmd, env=None):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=env or ENV)


seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

# ─── 1. Ensure imports include SmsLog and SmsConfig ────────────────────
if "from notifications.models import SmsLog" not in seed:
    seed = seed.replace(
        "from patients.models import Patient",
        "from patients.models import Patient\nfrom notifications.models import SmsLog"
    )

# ─── 2. Add SmsLog to the reset order ──────────────────────────────────
# We insert SmsLog right before TenantSequence/TenantSettings to ensure it's deleted early.
if "SmsLog," not in seed:
    seed = seed.replace(
        "        TenantSequence,\n        TenantSettings,\n        AuditLog,",
        "        TenantSequence,\n        TenantSettings,\n        SmsLog,\n        AuditLog,"
    )

seed_path.write_text(seed, encoding="utf-8")
print("   patched seed_demo.py (SmsLog reset order)")

# ─── 3. Run the seed ───────────────────────────────────────────────────
print("==> seed_demo --reset (NO_REDIS=1)")
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
sh(PY, "manage.py", "seed_demo", "--reset", env=seed_env)

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")