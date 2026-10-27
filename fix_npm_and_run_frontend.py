#!/usr/bin/env python3
"""
fix_npm_and_run_frontend.py
  - Ensures portable Node is on PATH
  - Resolves 'npm' → 'npm.cmd' via shutil.which (works on Windows)
  - Patches create_frontend.py to use the resolved executable
  - Runs create_frontend.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ─── 1. Portable Node location ─────────────────────────────────────────
NODE_DIR = Path.home() / "Documents" / "django" / "nodejs"
CREATE_FRONTEND = Path.cwd() / "create_frontend.py"

if not (NODE_DIR / "node.exe").exists():
    sys.exit(f"Portable Node not found at {NODE_DIR}.\n"
             f"Run get_portable_node.py first.")

# ─── 2. Add to PATH for this process + child processes ────────────────
os.environ["PATH"] = str(NODE_DIR) + os.pathsep + os.environ.get("PATH", "")

# ─── 3. Resolve npm (this is the fix) ─────────────────────────────────
npm_path = shutil.which("npm")
if not npm_path:
    sys.exit(
        "npm still not found even after adding nodejs to PATH.\n"
        f"Expected file: {NODE_DIR / 'npm.cmd'}\n"
        "Check that the extraction produced npm.cmd in that folder."
    )

print(f"==> node: {subprocess.check_output(['node', '--version'], text=True).strip()}")
print(f"==> npm:  {subprocess.check_output([npm_path, '--version'], text=True).strip()}")
print(f"==> npm resolved to: {npm_path}")

# ─── 4. Ensure create_frontend.py exists ──────────────────────────────
if not CREATE_FRONTEND.exists():
    sys.exit(
        f"create_frontend.py not found at {CREATE_FRONTEND}.\n"
        "Save the create_frontend.py script from the earlier message "
        "into the opd/ folder, then re-run this."
    )

# ─── 5. Patch create_frontend.py ──────────────────────────────────────
print("==> Patching create_frontend.py")
src = CREATE_FRONTEND.read_text(encoding="utf-8")
original = src

# 5a. Ensure shutil is imported
if "\nimport shutil\n" not in src:
    src = src.replace("\nimport subprocess\n", "\nimport subprocess\nimport shutil\n")

# 5b. Replace the npm sanity check
old_check = '''print("==> Checking Node.js")
try:
    subprocess.run(["node", "--version"], check=True, capture_output=True)
    subprocess.run(["npm", "--version"], check=True, capture_output=True)
except (FileNotFoundError, subprocess.CalledProcessError):
    sys.exit(
        "Node.js is not installed or not on PATH.\\n"
        "Install it from https://nodejs.org/ (LTS) or `winget install OpenJS.NodeJS.LTS`, "
        "then re-open PowerShell and re-run this script."
    )'''

new_check = '''print("==> Checking Node.js")
_npm = shutil.which("npm")
if not _npm:
    sys.exit("npm not on PATH. Run get_portable_node.py first.")
print("    node:", subprocess.check_output(["node", "--version"], text=True).strip())
print("    npm: ", subprocess.check_output([_npm, "--version"], text=True).strip())'''

if old_check in src:
    src = src.replace(old_check, new_check)
    print("    patched sanity check")
else:
    print("    [info] sanity check already patched or not found")

# 5c. Replace sh() so every command resolves via shutil.which
old_sh = '''def sh(*cmd, cwd=None):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=cwd or FRONTEND)'''

new_sh = '''def sh(*cmd, cwd=None):
    cmd = list(cmd)
    cmd[0] = shutil.which(str(cmd[0])) or cmd[0]
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=cwd or FRONTEND)'''

if old_sh in src:
    src = src.replace(old_sh, new_sh)
    print("    patched sh()")
else:
    print("    [info] sh() already patched or not found")

if src != original:
    CREATE_FRONTEND.write_text(src, encoding="utf-8")
    print("    saved create_frontend.py")
else:
    print("    create_frontend.py unchanged")

# ─── 6. Run it with the patched PATH ──────────────────────────────────
print()
print("==> Running create_frontend.py (this runs 'npm install', ~1 min)")
subprocess.run([sys.executable, str(CREATE_FRONTEND)],
               check=True, env=os.environ)

# ─── 7. Post-run instructions ─────────────────────────────────────────
print()
print("=" * 70)
print("SUCCESS — frontend created at:")
print(f"    {Path.home() / 'Documents' / 'django' / 'frontend'}")
print()
print("Start the dev server with THIS (note the PATH line):")
print()
print(f'    $env:PATH = "{NODE_DIR};" + $env:PATH')
print(f"    cd {Path.home() / 'Documents' / 'django' / 'frontend'}")
print("    npm run dev")
print()
print("(PowerShell resolves 'npm' → 'npm.cmd' automatically, so this")
print(" will work — unlike Python's subprocess.run, which needed the fix.)")
print("=" * 70)