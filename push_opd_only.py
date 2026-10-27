#!/usr/bin/env python3
"""
push_opd_only.py -- Create a fresh git repo inside opd/ and push ONLY opd to GitHub.
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

DJANGO = OPD.parent

def sh(*cmd, check=True, cwd=None):
    print("   $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], check=check, cwd=cwd or OPD)

# ─── 1. Move render.yaml into opd/ and rewrite paths ───────────────────
print("==> Moving render.yaml into opd/")
render_src = DJANGO / "render.yaml"
render_dst = OPD / "render.yaml"

if render_src.exists():
    content = render_src.read_text(encoding="utf-8")
    # repo root is now opd/, so remove "rootDir: opd" and simplify paths
    content = re.sub(r"^\s*rootDir:\s*opd\s*$", "", content, flags=re.MULTILINE)
    content = content.replace("rootDir: opd/frontend", "rootDir: frontend")
    # Use `bash build.sh` so it works regardless of executable bit
    content = content.replace('buildCommand: "./build.sh"', 'buildCommand: "bash build.sh"')
    render_dst.write_text(content, encoding="utf-8")
    print(f"   copied render.yaml → opd/render.yaml")
else:
    print("   [WARN] No render.yaml at django/. Skipping.")

# ─── 2. Write .gitignore inside opd/ ───────────────────────────────────
print("==> Writing opd/.gitignore")
gitignore = """\
# Python / Django
.venv/
venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Django runtime
db.sqlite3
db.sqlite3-journal
staticfiles/
media/
*.log

# Node / React
node_modules/
frontend/dist/
.vite/
*.local

# Environment
.env
.env.*
!.env.example

# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
"""
(OPD / ".gitignore").write_text(gitignore, encoding="utf-8")
print("   wrote opd/.gitignore")

# ─── 3. Guard against existing .git inside opd/ ────────────────────────
if (OPD / ".git").exists():
    print("\n   [ERROR] opd/.git already exists.")
    print("   Delete it first, then re-run:")
    print(f'      rmdir /s /q "{OPD / ".git"}"')
    sys.exit(1)

# ─── 4. Init git inside opd/ ───────────────────────────────────────────
print("==> Initializing git repo in opd/")
sh("git", "init")
sh("git", "branch", "-M", "main")
sh("git", "config", "user.email", "howard@nimbusopd.local")
sh("git", "config", "user.name", "Howard")
sh("git", "config", "http.postBuffer", "524288000")
sh("git", "config", "core.autocrlf", "false")

# ─── 5. Stage files (respects .gitignore) ──────────────────────────────
print("==> Staging files")
sh("git", "add", ".")

# sanity check: make sure nothing huge snuck through
result = subprocess.run(["git", "diff", "--cached", "--name-only"],
                        capture_output=True, text=True, cwd=OPD)
bad = [f for f in result.stdout.splitlines()
       if ".venv" in f or "node_modules" in f or "__pycache__" in f]
if bad:
    print(f"\n   [ERROR] {len(bad)} ignored files got staged. First: {bad[0]}")
    sys.exit(1)

# ensure build.sh is marked executable in git (works for Render)
sh("git", "update-index", "--add", "--chmod=+x", "build.sh", check=False)

# show total staged size for confidence
stat = subprocess.run(["git", "diff", "--cached", "--stat"],
                      capture_output=True, text=True, cwd=OPD)
for line in stat.stdout.splitlines()[-10:]:
    print("   " + line)

# ─── 6. Commit ────────────────────────────────────────────────────────
print("==> Committing")
sh("git", "commit", "-m", "Initial Nimbus OPD Cloud release")

# ─── 7. Configure remote & push ────────────────────────────────────────
print("==> Configuring remote")
sh("git", "remote", "add", "origin",
   "https://github.com/hmupeta/nimbus-opd.git", check=False)
sh("git", "remote", "set-url", "origin",
   "https://github.com/hmupeta/nimbus-opd.git")

print("==> Pushing to GitHub")
sh("git", "push", "-u", "origin", "main")

print("\n==> Done. Visit https://github.com/hmupeta/nimbus-opd to verify.")
print("==> Then go to https://dashboard.render.com → New → Blueprint → select that repo.")