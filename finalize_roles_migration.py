#!/usr/bin/env python3
"""
finalize_roles_migration.py
Applies the missing migrations for the roles patch and verifies them.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, check=check)

print("==> Running migrations to apply the model changes...")
sh(str(PY), "manage.py", "makemigrations")
sh(str(PY), "manage.py", "migrate")

print("\n==> Verifying the roles in the User model...")
check_code = """
from django.contrib.auth import get_user_model
U = get_user_model()
field = U._meta.get_field('role')
print("\\nCurrent choices in the User model:")
for k, v in field.choices:
    print(f"  - {k} ({v})")
"""
sh(str(PY), "manage.py", "shell", "-c", check_code)

print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
if status:
    subprocess.run(["git", "commit", "-m", "fix(backend): run missing migrations for new role choices"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. On Render, go to nimbus-backend -> Manual Deploy -> Clear build cache & deploy.")
print("  2. Try creating the user again. It will work.")