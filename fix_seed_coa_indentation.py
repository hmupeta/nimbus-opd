#!/usr/bin/env python3
"""
fix_seed_coa_indentation.py
  - Fixes the Chart of Accounts seeding in seed_demo.py to use `all_objects`.
  - This bypasses the TenantManager cache/context bug that caused the IntegrityError.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT,
                          capture_output=True, text=True)

# ─── 1. Fix seed_demo.py ───────────────────────────────────────────────
print("==> Fixing seed_demo.py")
seed = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
s = seed.read_text(encoding="utf-8")

# Remove the old broken block if it exists
pattern = re.compile(r"\n\s*# Seed Default Chart of Accounts.*?\)\n", re.DOTALL)
s = pattern.sub("\n", s)

# Insert the new block using all_objects to bypass ContextVar bugs
marker = "        with db_tenant_context(tenant):\n"
if marker in s:
    coa_block = """            # Seed Default Chart of Accounts
            accounts = [
                ("1000", "Cash & Bank", "asset"),
                ("1100", "Accounts Receivable", "asset"),
                ("4000", "Consultation Revenue", "revenue"),
                ("4100", "Pharmacy Revenue", "revenue"),
                ("4200", "Lab Revenue", "revenue"),
                ("4300", "Radiology Revenue", "revenue"),
            ]
            for code, name, type in accounts:
                # Use all_objects to bypass TenantManager and avoid duplicate inserts
                ChartOfAccount.all_objects.get_or_create(
                    tenant=tenant, code=code, defaults={"name": name, "type": type}
                )
"""
    s = s.replace(marker, marker + coa_block, 1)
    
    # Ensure ChartOfAccount is imported
    if "from accounting.models import ChartOfAccount" not in s:
        s = s.replace(
            "from patients.models import Patient",
            "from patients.models import Patient\nfrom accounting.models import ChartOfAccount"
        )
    
    seed.write_text(s, encoding="utf-8")
    print("   patched seed_demo.py (uses all_objects for COA)")
else:
    print("   [WARN] Could not find 'with db_tenant_context(tenant):' block in seed_demo.py")

# ─── 2. Run locally to confirm the fix ─────────────────────────────────
print("\n==> Running seed_demo locally to verify (NO_REDIS=1)")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
env = __import__("os").environ.copy()
env["NO_REDIS"] = "1"
r = subprocess.run([str(PY), "manage.py", "seed_demo"], cwd=ROOT, capture_output=True, text=True, env=env)

if r.returncode != 0:
    print("   ❌ Local seed failed:")
    print(r.stdout[-1000:])
    print(r.stderr[-1000:])
    sys.exit(1)
else:
    print("   ✓ Local seed succeeded. Last few lines:")
    for line in r.stdout.strip().splitlines()[-4:]:
        print("     " + line)

# ─── 3. Commit and Push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m", "fix(seed): resolve duplicate COA insert by using all_objects", check=False)
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")