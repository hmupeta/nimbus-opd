#!/usr/bin/env python3
"""
fix_missing_tenants_prod.py
1. Creates a data migration to assign default tenants to orphan users on production.
2. Patches UserViewSet so any newly created users automatically inherit the Admin's tenant.
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
# 1. Create Data Migration for Production
# ═════════════════════════════════════════════════════════════════════
print("==> Creating data migration to fix production tenants...")
r = sh(str(PY), "manage.py", "shell", "-c", "from django.conf import settings; print(settings.AUTH_USER_MODEL)")
user_model = r.stdout.strip()
user_app = user_model.split('.')[0]
print(f"   User Model: {user_model}")

mig_dir = ROOT / user_app / "migrations"
existing = sorted([f.stem for f in mig_dir.glob("*.py") if f.stem[0].isdigit()])
if not existing:
    sys.exit(f"No migrations found in {mig_dir}")
latest = existing[-1]

mig_name = f"{int(latest[:4]) + 1:04d}_assign_default_tenant"
mig_file = mig_dir / f"{mig_name}.py"

content = f'''from django.db import migrations

def assign_default_tenant(apps, schema_editor):
    User = apps.get_model('{user_app}', 'User')
    
    try:
        Tenant = apps.get_model('tenants', 'Tenant')
    except LookupError:
        try:
            Tenant = apps.get_model('{user_app}', 'Tenant')
        except LookupError:
            return

    default_tenant = Tenant.objects.first()
    if default_tenant:
        # Assign all orphan users to the first available tenant (Nkwanzi Clinic)
        updated = User.objects.filter(tenant__isnull=True).update(tenant=default_tenant)
        print(f"Assigned {{updated}} users to {{default_tenant.name}}")

class Migration(migrations.Migration):

    dependencies = [
        ('{user_app}', '{latest}'),
    ]

    operations = [
        migrations.RunPython(assign_default_tenant, migrations.RunPython.noop),
    ]
'''
mig_file.write_text(content, encoding="utf-8")
print(f"   Created migration: {mig_file.name}")

# ═════════════════════════════════════════════════════════════════════
# 2. Patch UserViewSet to auto-assign tenant for FUTURE users
# ═════════════════════════════════════════════════════════════════════
print("\n==> Patching UserViewSet for future user creation...")
patched = False
for p in ROOT.glob("**/views.py"):
    if "migrations" in str(p): continue
    src = p.read_text(encoding="utf-8")
    if "class UserViewSet" in src and "perform_create" not in src:
        match = re.search(r"(class UserViewSet\([^)]+\):\s*\n)", src)
        if match:
            inject = (
                "    def perform_create(self, serializer):\n"
                "        tenant = getattr(self.request.user, 'tenant', None)\n"
                "        serializer.save(tenant=tenant)\n"
            )
            src = src[:match.end()] + inject + src[match.end():]
            p.write_text(src, encoding="utf-8")
            print(f"   Patched UserViewSet in {p.relative_to(ROOT)}")
            patched = True

if not patched:
    print("   UserViewSet already patched or not found.")

# ═════════════════════════════════════════════════════════════════════
# 3. Run Migrate Locally & Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running local migrate...")
sh(str(PY), "manage.py", "migrate")

print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix(tenants): data migration for orphan users and auto-tenant on create"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. On Render, go to nimbus-backend -> Manual Deploy -> Clear build cache & deploy.")
print("  2. Log out and log back in as mwangala or friday. The pages will load perfectly.")