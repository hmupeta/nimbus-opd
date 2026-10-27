#!/usr/bin/env python3
"""
fix_line_endings_and_push.py -- Convert critical build files to LF and push.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

def sh(*cmd, check=True):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD, capture_output=True, text=True)

def print_result(r):
    if r.stdout.strip():
        print("   " + r.stdout.strip().replace("\n", "\n   "))
    if r.stderr.strip() and r.returncode != 0:
        print("   ERR: " + r.stderr.strip().replace("\n", "\n        "))

# ─── 1. Write .gitattributes ───────────────────────────────────────────
print("==> Writing .gitattributes")
gitattributes = """\
# Normalize line endings on commit / checkout
* text=auto

# Force LF for scripts and configs (Render runs on Linux)
*.sh         text eol=lf
*.bash       text eol=lf
Dockerfile   text eol=lf
*.py         text eol=lf
*.yml        text eol=lf
*.yaml       text eol=lf
*.txt        text eol=lf
*.toml       text eol=lf
*.json       text eol=lf
*.md         text eol=lf
"""
(OPD / ".gitattributes").write_bytes(gitattributes.encode("utf-8"))
print("   wrote .gitattributes")

# ─── 2. Force LF endings on critical files ─────────────────────────────
print("==> Normalizing critical files to LF on disk")
critical = ["build.sh", "requirements.txt", "render.yaml", ".gitignore"]
for fname in critical:
    p = OPD / fname
    if not p.exists():
        print(f"   [skip] {fname} missing")
        continue
    raw = p.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if raw != normalized:
        p.write_bytes(normalized)
        print(f"   {fname}: converted CRLF → LF")
    else:
        print(f"   {fname}: already LF")

# ─── 3. Rewrite build.sh with safer contents ──────────────────────────
print("==> Rewriting build.sh with diagnostics")
build_sh = """#!/usr/bin/env bash
set -euo pipefail

echo "→ Upgrading pip..."
pip install --quiet --upgrade pip

echo "→ Installing dependencies..."
pip install -r requirements.txt

echo "→ Verifying Django installation..."
python -c "import django; print('Django', django.get_version())"

echo "→ Collecting static files..."
python manage.py collectstatic --no-input

echo "→ Build complete."
"""
(OPD / "build.sh").write_bytes(build_sh.encode("utf-8"))  # noqa: explicit bytes → no CRLF
print("   wrote build.sh (LF, with Django verification)")

# ─── 4. Renormalize git index ──────────────────────────────────────────
print("==> Renormalizing git index (adds .gitattributes, LF-corrected files)")
r = sh("git", "add", "--renormalize", ".")
print_result(r)
r = sh("git", "add", "-A")
print_result(r)

# ─── 5. Verify no CRLF remains in tracked text files ───────────────────
print("==> Verifying no CRLF in tracked files")
r = sh("git", "ls-files", "--eol")
crlf_files = [line for line in r.stdout.splitlines() if "w/crlf" in line]
if crlf_files:
    print("   [WARN] Files still have CRLF:")
    for line in crlf_files:
        print("      " + line)
else:
    print("   ✓ All tracked files use LF")

# ─── 6. Commit and push ────────────────────────────────────────────────
print("==> Committing")
r = sh("git", "commit", "-m",
       "fix(build): normalize to LF endings; add .gitattributes; harden build.sh")
print_result(r)

print("==> Pushing to origin/main")
r = sh("git", "push", "origin", "main")
print_result(r)

# ─── 7. Print new commit hash ──────────────────────────────────────────
r = sh("git", "rev-parse", "--short", "HEAD")
print(f"\n==> New commit: {r.stdout.strip()}")
print("==> On Render:")
print("   1. Open nimbus-backend → Manual Deploy → Clear build cache & deploy")
print("   2. Watch for '→ Verifying Django installation... Django 6.x.x'")
print("   3. If it shows 'Django 6.1.x', the build is fixed")