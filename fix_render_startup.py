#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
ry = ROOT / "render.yaml"

if not ry.exists():
    sys.exit("Run this from inside the opd/ directory")

y = ry.read_text(encoding="utf-8")

# The safe startup command (only migrations, then gunicorn)
old_cmd = "python manage.py migrate --noinput && python manage.py fix_stuck_orders && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
new_cmd = "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"

if old_cmd in y:
    y = y.replace(old_cmd, new_cmd)
    ry.write_text(y, encoding="utf-8")
    print("✅ Removed background scripts from startup command.")
    
    print("Committing and pushing...")
    subprocess.run(["git", "add", "render.yaml"], cwd=ROOT)
    subprocess.run(["git", "commit", "-m", "fix: remove dangerous startup scripts, keep only migrate"], cwd=ROOT)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
    print("✅ Pushed. You can now manually deploy this fix on Render.")
else:
    print("⚠️ Startup command is already clean.")