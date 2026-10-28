#!/usr/bin/env python3
"""
fix_tenant_transaction.py
  - Ensures ATOMIC_REQUESTS is kept even when using DATABASE_URL
  - Fixes the next_sequence function to not re-query on a broken transaction
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD,
                          capture_output=True, text=True)

# ─── 1. Fix settings.py to preserve ATOMIC_REQUESTS ────────────────────
print("==> Patching config/settings.py")
sp = OPD / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")

old_db = '''if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=600,
        ssl_require=True,
    )'''

new_db = '''if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=600,
        ssl_require=True,
    )
    # CRITICAL: dj_database_url drops custom settings, so we must re-apply this.
    # Without ATOMIC_REQUESTS, the Tenant RLS context is immediately lost.
    DATABASES["default"]["ATOMIC_REQUESTS"] = True'''

if old_db in s:
    s = s.replace(old_db, new_db)
    sp.write_text(s, encoding="utf-8")
    print("   patched settings.py (restored ATOMIC_REQUESTS)")
else:
    print("   [WARN] Could not find exact DATABASE_URL block in settings.py")

# ─── 2. Fix next_sequence in patients/models.py ────────────────────────
print("==> Patching patients/models.py")
pm = OPD / "patients" / "models.py"
p_content = pm.read_text(encoding="utf-8")

# We'll replace the broken try/except block with a clean, atomic version
# Match the function from "def next_sequence" to the start of the next function or class
pattern = re.compile(r"def next_sequence\(tenant, scope: str\) -> int:.*?(?=\nclass |\ndef |\Z)", re.DOTALL)

new_seq = '''def next_sequence(tenant, scope: str) -> int:
    with transaction.atomic():
        seq, _ = TenantSequence.objects.select_for_update().get_or_create(
            tenant=tenant, scope=scope,
        )
        seq.last += 1
        seq.save(update_fields=["last"])
        return seq.last
'''

if pattern.search(p_content):
    p_content = pattern.sub(new_seq, p_content, count=1)
    pm.write_text(p_content, encoding="utf-8")
    print("   patched next_sequence (removed broken try/except)")
else:
    print("   [WARN] Could not find next_sequence block in patients/models.py")

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(db): preserve ATOMIC_REQUESTS for RLS; clean up next_sequence",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("\nOnce Live, refresh the frontend and try to create a patient again.")