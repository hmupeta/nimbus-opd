#!/usr/bin/env python3
"""
fix_radiology_import.py -- Add RadiologyExam to imports in views.py.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = __import__("os").environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")

# Fix import line
if "RadiologyExam" not in v.split("class RadiologyExamViewSet")[0]:
    v = v.replace(
        "from radiology.models import RadiologyOrder",
        "from radiology.models import RadiologyExam, RadiologyOrder"
    )
    # If that exact import doesn't exist, try another fallback
    if "from radiology.models import RadiologyExam" not in v:
        # Find the existing radiology import and add RadiologyExam
        v = v.replace(
            "from radiology.models import RadiologyOrder,",
            "from radiology.models import RadiologyExam, RadiologyOrder,"
        )
    vp.write_text(v, encoding="utf-8")
    print("   patched radiology import in api/views.py")
else:
    print("   import already present")

# Verify
print("==> manage.py check")
subprocess.run([str(PY), "manage.py", "check"], check=True, env=ENV)

# Run migrations
print("==> makemigrations radiology")
subprocess.run([str(PY), "manage.py", "makemigrations", "radiology"], check=True, env=ENV)

print("==> migrate")
subprocess.run([str(PY), "manage.py", "migrate"], check=True, env=ENV)

print("==> Done. Push and redeploy both services.")