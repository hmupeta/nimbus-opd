#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

OPD = Path.cwd()
if not (OPD / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory.")

ry = OPD / "render.yaml"
content = ry.read_text(encoding="utf-8")

old_cmd = 'startCommand: "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"'
new_cmd = 'startCommand: "python manage.py migrate --noinput && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"'

if old_cmd in content:
    content = content.replace(old_cmd, new_cmd)
    ry.write_text(content, encoding="utf-8")
    print("✅ Updated render.yaml to auto-seed database on startup.")
    
    subprocess.run(["git", "add", "render.yaml"], cwd=OPD)
    subprocess.run(["git", "commit", "-m", "fix(render): auto-seed database on startup for free tier"], cwd=OPD)
    subprocess.run(["git", "push", "origin", "main"], cwd=OPD)
    print("🚀 Pushed to GitHub. Render will auto-deploy shortly.")
else:
    print("⚠️ Could not find the exact startCommand string in render.yaml.")