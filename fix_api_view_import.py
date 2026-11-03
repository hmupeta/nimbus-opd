#!/usr/bin/env python3
"""
fix_api_view_import.py
Fixes the missing imports in tenants/views.py and pushes the changes.
"""
import subprocess, sys, shutil, os
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")
FRONTEND = ROOT / "frontend"
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python")

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

# ═════════════════════════════════════════════════════════════════════
# 1. Fix the missing imports in tenants/views.py
# ═════════════════════════════════════════════════════════════════════
print("==> Fixing imports in tenants/views.py")
views_path = ROOT / "tenants" / "views.py"
src = views_path.read_text(encoding="utf-8")

required_imports = (
    "from rest_framework.views import APIView\n"
    "from rest_framework.response import Response\n"
    "from rest_framework.permissions import IsAuthenticated\n"
)

if "from rest_framework.views import APIView" not in src:
    # Prepend the imports to the top of the file
    src = required_imports + "\n" + src
    views_path.write_text(src, encoding="utf-8")
    print("   Prepended missing REST framework imports.")
else:
    print("   Imports already exist.")

# ═════════════════════════════════════════════════════════════════════
# 2. Run Django checks & migrations
# ═════════════════════════════════════════════════════════════════════
print("\n==> Running Django checks and migrations")
subprocess.run([str(PY), "manage.py", "makemigrations", "tenants"], cwd=ROOT, check=False)
subprocess.run([str(PY), "manage.py", "migrate"], cwd=ROOT, check=False)

# ═════════════════════════════════════════════════════════════════════
# 3. Vite Build
# ═════════════════════════════════════════════════════════════════════
npm = npm_path()
if npm:
    print("\n==> Running Vite build...")
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)
    if r.returncode == 0:
        print("   ✓ Build succeeded!")
    else:
        print("   ❌ Build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-15:]:
            print("     " + line)

# ═════════════════════════════════════════════════════════════════════
# 4. Commit and Push
# ═════════════════════════════════════════════════════════════════════
print("\n==> Committing and pushing")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

if status:
    subprocess.run(["git", "commit", "-m", "fix(backend): add missing APIView import in tenants/views.py"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")

subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. Deploy backend and frontend on Render.")
print("  2. Log in as the Admin.")
print("  3. Click on 'Integrations' in the sidebar. You will now see the secure settings page to enter your SMS and WhatsApp API keys!")