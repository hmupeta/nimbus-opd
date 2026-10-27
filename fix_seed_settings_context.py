#!/usr/bin/env python3
"""
fix_seed_settings_context.py -- move TenantSettings creation inside the
                                 db_tenant_context so RLS WITH CHECK passes.
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


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


seed_path = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
seed = seed_path.read_text(encoding="utf-8")

# ── Fix 1: tenant "demo" ───────────────────────────────────────────────
old_demo = '''        TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"},
        )

        with db_tenant_context(tenant):
            users = self._demo_users(tenant)'''

new_demo = '''        with db_tenant_context(tenant):
            TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"},
            )
            users = self._demo_users(tenant)'''

# ── Fix 2: tenant "clinic-b" ───────────────────────────────────────────
old_b = '''        TenantSettings.objects.get_or_create(
            tenant=tenant,
            defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"},
        )

        with db_tenant_context(tenant):
            _make_user(tenant, "admin@clinic-b.local", "admin",'''

new_b = '''        with db_tenant_context(tenant):
            TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={"timezone": "Africa/Lusaka", "currency_code": "ZMW"},
            )
            _make_user(tenant, "admin@clinic-b.local", "admin",'''

replaced = 0
if old_demo in seed:
    seed = seed.replace(old_demo, new_demo)
    replaced += 1
if old_b in seed:
    seed = seed.replace(old_b, new_b)
    replaced += 1

if replaced == 2:
    seed_path.write_text(seed, encoding="utf-8")
    print(f"   patched {seed_path.relative_to(ROOT)} ({replaced}/2 blocks)")
else:
    print(f"   [WARN] only {replaced}/2 blocks matched — inspect seed_demo.py by hand")

print("==> seed_demo --reset")
sh(PY, "manage.py", "seed_demo", "--reset")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")