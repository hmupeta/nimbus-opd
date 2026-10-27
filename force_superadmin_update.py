#!/usr/bin/env python3
"""
force_superadmin_update.py
  - Change seed_demo.py to use update_or_create for superadmin
    (so the password is always 'demo', even if the user exists)
  - Push to GitHub
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

# ─── 1. Update seed_demo.py ────────────────────────────────────────────
print("==> Updating seed_demo.py to force-create superadmin")
seed = OPD / "tenants" / "management" / "commands" / "seed_demo.py"
s = seed.read_text(encoding="utf-8")

# Remove the old _ensure_superadmin method
pattern = re.compile(r"    def _ensure_superadmin\(self\):.*?(?=\n    def |\nclass |\Z)", re.DOTALL)
s = pattern.sub("", s)

# Insert the new, bulletproof method
new_method = '''    def _ensure_superadmin(self):
        """Force-create or update the Platform Admin with NO tenant."""
        from django.contrib.auth.hashers import make_password
        from tenants.models import User
        
        user, created = User.objects.update_or_create(
            email="superadmin@nimbus.local",
            defaults={
                "password": make_password("demo"),
                "first_name": "Super",
                "last_name": "Admin",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_platform_admin": True,
                "tenant": None,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                "   [superadmin] CREATED: superadmin@nimbus.local / demo"))
        else:
            self.stdout.write(self.style.SUCCESS(
                "   [superadmin] UPDATED password to 'demo'"))

'''
# Add it back right before "# ── tenant A ─"
anchor = "    # ── tenant A ───────────────────────────────────────────────────────"
if anchor in s:
    s = s.replace(anchor, new_method + anchor, 1)
else:
    # Fallback: append before class ends
    s += "\n" + new_method

# Ensure the handle() method calls it
if "self._ensure_superadmin()" not in s:
    s = s.replace("        self._seed_demo()\n",
                  "        self._ensure_superadmin()\n        self._seed_demo()\n", 1)

seed.write_text(s, encoding="utf-8")
print("   patched seed_demo.py")

# ─── 2. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
sh("git", "add", ".")

r = sh("git", "commit", "-m",
       "fix(seed): force-create/update superadmin@nimbus.local with password 'demo'",
       check=False)
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
out = (r.stdout or r.stderr or "").strip()
if out:
    print("   " + out.replace("\n", "\n   "))

r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n✅ Pushed: {r.stdout.strip()}")

print("\n" + "=" * 60)
print("NEXT STEPS ON RENDER")
print("=" * 60)
print("1. Open nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("2. Watch the logs. You should see:")
print("      [superadmin] CREATED: superadmin@nimbus.local / demo")
print("3. Sign out of the frontend and log in with:")
print("      Email:    superadmin@nimbus.local")
print("      Password: demo")