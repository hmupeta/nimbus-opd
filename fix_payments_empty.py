#!/usr/bin/env python3
"""
fix_payments_empty.py
1. Inspects the database to see the payments and user tenants.
2. Fixes the Payment manager to use PaymentQuerySet (preserves default filtering).
3. Commits and pushes.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd):
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True)

# ═════════════════════════════════════════════════════════════════════
# 1. Inspect the Database
# ═════════════════════════════════════════════════════════════════════
print("==> Checking payments in the database...")
code = """
from billing.models import Payment
from django.contrib.auth import get_user_model
U = get_user_model()

print(f"Total payments in DB: {Payment.objects.count()}")
for p in Payment.objects.all()[:10]:
    print(f" - ID: {p.id}, Amount: {p.amount}, Status: {p.status}, Tenant: {getattr(p, 'tenant', 'N/A')}")
    
print("\\nRecent users and their tenants:")
for u in U.objects.order_by('-id')[:5]:
    print(f" - {u.username} (Role: {getattr(u, 'role', 'N/A')}, Tenant: {getattr(u, 'tenant', 'N/A')})")
"""
r = sh(str(PY), "manage.py", "shell", "-c", code)
print(r.stdout)
if r.stderr:
    print(r.stderr)

# ═════════════════════════════════════════════════════════════════════
# 2. Fix the Manager
# ═════════════════════════════════════════════════════════════════════
print("==> Fixing PaymentManager to PaymentQuerySet...")
mp = ROOT / "billing" / "models.py"
src = mp.read_text(encoding="utf-8")

if "class PaymentManager" in src:
    src = src.replace("class PaymentManager(models.Manager):", "class PaymentQuerySet(models.QuerySet):")
    src = src.replace("objects = PaymentManager()", "objects = PaymentQuerySet.as_manager()")
    mp.write_text(src, encoding="utf-8")
    print("   Updated models.py to use PaymentQuerySet.")
elif "class PaymentQuerySet" in src:
    print("   models.py already uses PaymentQuerySet.")
else:
    print("   [WARN] Could not find PaymentManager in models.py")

# ═════════════════════════════════════════════════════════════════════
# 3. Commit & Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix(backend): use QuerySet manager to preserve tenant filtering"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. On Render, go to nimbus-backend -> Manual Deploy -> Clear build cache & deploy.")
print("  2. Refresh the Payments page. It should now be populated.")