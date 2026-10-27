#!/usr/bin/env python3
"""
push_render_fix.py -- Overwrite render.yaml with free-tier-compatible config
                      and push to GitHub.
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
    return subprocess.run([str(c) for c in cmd], check=check, cwd=OPD)

# ─── 1. Write the CORRECT render.yaml ──────────────────────────────────
print("==> Writing corrected render.yaml")
correct_yaml = """\
databases:
  - name: nimbus-db
    databaseName: nimbus
    user: nimbus_admin
    plan: free

services:
  # 1. Redis
  - type: redis
    name: nimbus-redis
    plan: free
    ipAllowList: []

  # 2. Django Backend
  - type: web
    name: nimbus-backend
    env: python
    plan: free
    buildCommand: "bash build.sh"
    startCommand: "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nimbus-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: nimbus-redis
          property: connectionString
      - key: DJANGO_SECRET_KEY
        generateValue: true
      - key: DJANGO_DEBUG
        value: "0"
      - key: PYTHON_VERSION
        value: "3.13.0"

  # 3. React Frontend
  - type: web
    name: nimbus-frontend
    runtime: static
    buildCommand: "npm install && npm run build"
    staticPublishPath: dist
    rootDir: frontend
    envVars:
      - key: VITE_API_BASE
        value: "https://nimbus-backend.onrender.com"
"""
(OPD / "render.yaml").write_text(correct_yaml, encoding="utf-8")
print("   wrote render.yaml (no preDeployCommand)")

# ─── 2. Verify the file is what we expect ──────────────────────────────
content = (OPD / "render.yaml").read_text(encoding="utf-8")
checks = {
    "preDeployCommand removed": "preDeployCommand" not in content,
    "startCommand runs migrate": "migrate --noinput" in content,
    "gunicorn binds to PORT": "0.0.0.0:$PORT" in content,
    "frontend is static": "runtime: static" in content,
    "no invalid plan on frontend": "name: nimbus-frontend\n    runtime: static" in content
    and "plan: free" not in content.split("name: nimbus-frontend")[1],
}
for label, ok in checks.items():
    print(f"   [{'✓' if ok else '✗'}] {label}")
    if not ok:
        sys.exit(f"YAML check failed: {label}")

# ─── 3. Commit and push ────────────────────────────────────────────────
print("\n==> Committing")
sh("git", "add", "render.yaml")
result = subprocess.run(
    ["git", "commit", "-m",
     "fix(render): remove preDeployCommand, run migrate in startCommand (free tier)"],
    cwd=OPD, capture_output=True, text=True
)
print("   " + (result.stdout.strip() or result.stderr.strip() or "(nothing to commit)"))

print("==> Pushing")
sh("git", "push", "origin", "main")

# ─── 4. Print the new commit hash for reference ────────────────────────
commit_hash = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],
    cwd=OPD, capture_output=True, text=True
).stdout.strip()
print(f"\n==> New commit on GitHub: {commit_hash}")
print("==> Now on Render:")
print("   1. Go to Blueprints → nimbus-production")
print("   2. Click 'Manual Sync' (or 'Apply')")
print("   3. Render will rebuild the backend without preDeployCommand")