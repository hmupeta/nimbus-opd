#!/usr/bin/env python3
"""
strip_backslash_and_push.py -- Fix the leading backslash in VisitTimeline.tsx
and push.
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

FRONTEND = ROOT / "frontend"
VP = FRONTEND / "src" / "pages" / "VisitTimeline.tsx"

# ─── 1. Strip stray leading backslash ──────────────────────────────────
print("==> Fixing stray backslash in VisitTimeline.tsx")
raw = VP.read_bytes()

if raw.startswith(b"\\\r\n"):
    VP.write_bytes(raw[3:])
    print("   stripped leading '\\' + CRLF")
elif raw.startswith(b"\\\n"):
    VP.write_bytes(raw[2:])
    print("   stripped leading '\\' + LF")
elif raw.startswith(b"\\"):
    # Edge case — find the first newline after the backslash
    idx = raw.find(b"\n")
    if idx > 0:
        VP.write_bytes(raw[idx + 1:])
        print("   stripped line starting with '\\'")
    else:
        print("   [WARN] No newline found after backslash")
else:
    print("   no leading backslash (already clean)")

# ─── 2. Verify no other .tsx files have the same issue ─────────────────
print("\n==> Scanning all .tsx files for leading backslashes")
pages = FRONTEND / "src" / "pages"
fixed = 0
for f in pages.glob("*.tsx"):
    r = f.read_bytes()
    if r.startswith(b"\\\r\n"):
        f.write_bytes(r[3:])
        print(f"   FIXED: {f.name}")
        fixed += 1
    elif r.startswith(b"\\\n"):
        f.write_bytes(r[2:])
        print(f"   FIXED: {f.name}")
        fixed += 1

if fixed == 0:
    print("   no other files affected")

# ─── 3. Verify with local Vite build ───────────────────────────────────
print("\n==> Running local Vite build")
npm = shutil.which("npm")
if not npm:
    node_dir = Path.home() / "Documents" / "django" / "nodejs"
    if (node_dir / "npm.cmd").exists():
        npm = str(node_dir / "npm.cmd")

if npm:
    import os
    env = os.environ.copy()
    env["PATH"] = str(Path(npm).parent) + os.pathsep + env.get("PATH", "")
    r = subprocess.run(
        [npm, "run", "build"],
        cwd=FRONTEND, capture_output=True, text=True, env=env,
    )
    if r.returncode == 0:
        print("   ✓ Local Vite build succeeded!")
        for line in (r.stdout or "").strip().splitlines()[-4:]:
            print(f"     {line}")
    else:
        print("   ❌ Local Vite build failed:")
        for line in (r.stdout + r.stderr).splitlines()[-20:]:
            print(f"     {line}")
        sys.exit(1)
else:
    print("   [skip] npm not found")

# ─── 4. Commit and push ────────────────────────────────────────────────
print("\n==> Committing and pushing")
def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=ROOT,
                          capture_output=True, text=True)

sh("git", "add", ".")
r = sh("git", "commit", "-m", "fix(ui): strip stray leading backslash from VisitTimeline.tsx", check=False)
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

r = sh("git", "push", "origin", "main")
if r.stdout.strip():
    print("   " + r.stdout.strip().replace("\n", "\n   "))

print("\n✅ Pushed!")
print("\nNEXT STEPS ON RENDER:")
print("  → nimbus-frontend → Manual Deploy → Clear build cache & deploy")