#!/usr/bin/env python3
"""
fix_tenant_assignment.py
1. Checks users and assigns missing tenants to the default clinic.
2. Forcibly fixes PaymentViewSet permissions.
"""
import subprocess, sys, re
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd):
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True)

# ═════════════════════════════════════════════════════════════════════
# 1. Inspect and Fix Tenants
# ═════════════════════════════════════════════════════════════════════
print("==> Checking and fixing user tenants...")
code = """
from django.contrib.auth import get_user_model
from tenants.models import Tenant

U = get_user_model()
# Find a tenant to use as the default
default_tenant = Tenant.objects.first()

if not default_tenant:
    print("No tenants found in the database!")
else:
    print(f"Using default tenant: {default_tenant.name}")
    
    # Find users without a tenant
    orphaned_users = U.objects.filter(tenant__isnull=True)
    for u in orphaned_users:
        u.tenant = default_tenant
        u.save()
        print(f" -> Assigned {u.username} ({u.role}) to {default_tenant.name}")
        
    print("\\nCurrent Users and their Tenants:")
    for u in U.objects.all():
        tenant_name = u.tenant.name if u.tenant else "NONE"
        print(f" - {u.username.ljust(15)} | Role: {u.role.ljust(15)} | Tenant: {tenant_name}")
"""
r = sh(str(PY), "manage.py", "shell", "-c", code)
print(r.stdout)
if r.stderr:
    print(r.stderr)

# ═════════════════════════════════════════════════════════════════════
# 2. Forcibly Fix PaymentViewSet Permissions
# ═════════════════════════════════════════════════════════════════════
print("\n==> Forcibly fixing PaymentViewSet permissions...")
vp = ROOT / "billing" / "views.py"
if vp.exists():
    src = vp.read_text(encoding="utf-8")
    if "class PaymentViewSet" in src:
        # Check if permission_classes = [IsAuthenticated] exists
        if "permission_classes = [IsAuthenticated]" not in src:
            # Inject right after class definition
            src = re.sub(
                r"(class PaymentViewSet\([^)]+\):\s*\n)",
                r"\1    permission_classes = [IsAuthenticated]\n",
                src, count=1
            )
            vp.write_text(src, encoding="utf-8")
            print("   Injected 'permission_classes = [IsAuthenticated]' into PaymentViewSet.")
        else:
            print("   PaymentViewSet already has IsAuthenticated.")
    else:
        print("   [WARN] PaymentViewSet not found in billing/views.py")

# ═════════════════════════════════════════════════════════════════════
# 3. Commit & Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix(backend): assign tenants to orphan users and fix payment permissions"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. On Render, go to nimbus-backend -> Manual Deploy -> Clear build cache & deploy.")
print("  2. Log out and log back in as the Accountant.")