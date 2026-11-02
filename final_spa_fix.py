#!/usr/bin/env python3
"""
final_spa_fix.py
Adds the SPA _redirects file, properly injects the Node path for the build, and pushes.
"""
import subprocess, sys, shutil, os
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
PUBLIC_DIR = FRONTEND / "public"

def npm_path():
    p = shutil.which("npm")
    if p: return p
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists(): return str(c)
    return None

npm = npm_path()
if not npm:
    sys.exit("npm not found")

# 1. Ensure public directory and _redirects file exist
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
redirects_file = PUBLIC_DIR / "_redirects"
redirects_file.write_text("/*    /index.html   200\n", encoding="utf-8")
print(f"==> Created {redirects_file.relative_to(ROOT)}")

# 2. Run Vite build WITH the correct environment PATH
print("\n==> Running Vite build...")
env = os.environ.copy()
# This is the critical line that was missing: add Node to PATH so npm can find it
env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")

r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True, env=env)

if r.returncode == 0:
    print("   ✓ Build succeeded!")
else:
    print("   ❌ Build failed. Here is the error:")
    for line in (r.stdout + r.stderr).splitlines()[-15:]:
        print("     " + line)
    sys.exit(1)

# 3. Commit and push
print("\n==> Committing and pushing...")
subprocess.run(["git", "add", "."], cwd=ROOT, check=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()

if status:
    subprocess.run(["git", "commit", "-m", "fix(ui): add SPA _redirects to fix 404 on refresh"], cwd=ROOT, check=True)
else:
    print("   (nothing to commit)")

subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)

print("\n✅ Done.")
print("\nNEXT STEPS:")
print("  1. Wait for Render to auto-deploy the frontend.")
print("  2. Hard refresh (Ctrl+F5) on /login. It will load perfectly.")