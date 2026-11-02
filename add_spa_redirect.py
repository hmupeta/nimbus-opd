#!/usr/bin/env python3
"""
add_spa_redirect.py
Creates a _redirects file in the Vite public folder.
Render reads this natively to fix React Router "Not Found" on refresh.
"""
import subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
PUBLIC_DIR = FRONTEND / "public"

# 1. Ensure public directory exists
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

# 2. Create the _redirects file
redirects_file = PUBLIC_DIR / "_redirects"
content = "/*    /index.html   200\n"

redirects_file.write_text(content, encoding="utf-8")
print(f"==> Created {redirects_file.relative_to(ROOT)}")
print("    Rule: /* -> /index.html (status 200)")

# 3. Run Vite build to verify it gets copied to dist/
print("\n==> Running Vite build to verify...")
import shutil
npm = shutil.which("npm")
if not npm:
    for c in [
        Path.home() / "Documents" / "django" / "nodejs" / "npm.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "npm.cmd",
    ]:
        if c.exists():
            npm = str(c); break

if npm:
    r = subprocess.run([npm, "run", "build"], cwd=FRONTEND, capture_output=True, text=True)
    if r.returncode == 0:
        print("   ✓ Build OK")
        # Verify it was copied
        dist_redirects = FRONTEND / "dist" / "_redirects"
        if dist_redirects.exists():
            print(f"   ✓ Verified {dist_redirects.relative_to(ROOT)} exists in build output")
        else:
            print("   ⚠️ Warning: _redirects was not found in dist/. Check your vite.config build settings.")
    else:
        print("   ❌ Build failed")
        sys.exit(1)

# 4. Commit & Push
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
print("  1. Wait for Render to auto-deploy the frontend (or trigger a manual deploy).")
print("  2. Hard refresh (Ctrl+F5) on any page (like /login). It will load perfectly.")