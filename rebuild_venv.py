#!/usr/bin/env python3
"""
rebuild_venv.py -- Nuclear option: rebuild .venv from scratch.
Run this with SYSTEM Python (not the venv python).
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

VENV = ROOT / ".venv"

# ─── 1. Rename the old venv (safer than delete — Windows file locks) ──
if VENV.exists():
    backup = ROOT / f".venv_backup_{int(time.time())}"
    print(f"==> Renaming old venv to {backup.name}")
    try:
        VENV.rename(backup)
        print("   ✓ old venv moved aside")
    except PermissionError:
        print(f"   ❌ Cannot rename .venv — is a process using it?")
        print("   Close all terminals, VS Code, and Python processes, then try again.")
        sys.exit(1)
else:
    print("==> No existing .venv to move")

# ─── 2. Create a new venv ──────────────────────────────────────────────
print("\n==> Creating new .venv")
try:
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    print("   ✓ venv created")
except subprocess.CalledProcessError as e:
    print(f"   ❌ Failed to create venv: {e}")
    print("   Make sure Python is installed: python --version")
    sys.exit(1)

# ─── 3. Find the venv Python ───────────────────────────────────────────
if sys.platform == "win32":
    VENV_PY = VENV / "Scripts" / "python.exe"
else:
    VENV_PY = VENV / "bin" / "python"

if not VENV_PY.exists():
    sys.exit(f"   ❌ venv python not found at {VENV_PY}")

print(f"   using: {VENV_PY}")

# ─── 4. Upgrade pip & install requirements ─────────────────────────────
print("\n==> Upgrading pip inside venv")
subprocess.run([str(VENV_PY), "-m", "pip", "install", "--quiet", "--upgrade", "pip"], check=True)
print("   ✓ pip upgraded")

REQ = ROOT / "requirements.txt"
if not REQ.exists():
    sys.exit("   ❌ requirements.txt not found")

print("\n==> Installing requirements (may take 2–3 minutes)")
try:
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "-r", str(REQ)], check=True)
    print("   ✓ requirements installed")
except subprocess.CalledProcessError:
    print("   ⚠ Some packages failed to install (network?). Retrying with retries...")
    subprocess.run(
        [str(VENV_PY), "-m", "pip", "install", "--retries", "5", "--timeout", "60", "-r", str(REQ)],
        check=True
    )
    print("   ✓ requirements installed on retry")

# ─── 5. Verify Django loads ────────────────────────────────────────────
print("\n==> Verifying Django installation")
r = subprocess.run([str(VENV_PY), "-c", "import django; print(django.get_version())"],
                   capture_output=True, text=True)
if r.returncode == 0:
    print(f"   ✓ Django {r.stdout.strip()} installed")
else:
    print(f"   ❌ Django check failed: {r.stderr}")
    sys.exit(1)

# ─── 6. Run manage.py check ────────────────────────────────────────────
print("\n==> Running manage.py check")
env = os.environ.copy()
env.setdefault("DB_NAME", "opd")
env.setdefault("DB_USER", "opd_owner")
env.setdefault("DB_PASSWORD", "opd_owner")
r = subprocess.run([str(VENV_PY), "manage.py", "check"], env=env, capture_output=True, text=True)
if r.returncode == 0:
    print("   ✓ " + (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "OK"))
else:
    print("   ⚠ manage.py check reported issues:")
    for line in (r.stderr or r.stdout).splitlines()[-10:]:
        print(f"     {line}")

# ─── 7. Print next steps ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("✅ VENV REBUILT SUCCESSFULLY")
print("=" * 60)
print("\nNext steps (in a NEW PowerShell window):")
print(f"    cd {ROOT}")
print("    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process")
print("    .\\.venv\\Scripts\\Activate.ps1")
print()
print("You should see '(.venv)' appear in your prompt.")
print()
print(f"The old venv is preserved at: {ROOT / backup.name if VENV.exists() else 'N/A'}")
print("You can delete it once the new venv is confirmed working.")