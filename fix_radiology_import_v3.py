#!/usr/bin/env python3
"""
fix_radiology_import_v3.py -- Force-inject the RadiologyExam model import.
"""
from __future__ import annotations
import os
import re
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

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

vp = ROOT / "api" / "views.py"
v = vp.read_text(encoding="utf-8")
lines = v.split("\n")

# ─── 1. Show all existing imports from radiology.models and .serializers ─
print("==> Current radiology + serializer imports in api/views.py:")
for i, line in enumerate(lines[:80], 1):
    if ("from radiology" in line
            or "RadiologyExam" in line
            or "RadiologyOrder" in line
            or "RadiologyExamSerializer" in line):
        print(f"   L{i:3}: {line}")
print()

# ─── 2. Check whether RadiologyExam is TRULY imported ──────────────────
# Match ONLY radiology.models imports
radiology_model_import_re = re.compile(
    r"from\s+radiology\.models\s+import\s+(.+?)(?:\n|$)", re.MULTILINE
)
found_model_import = False
for m in radiology_model_import_re.finditer(v):
    if "RadiologyExam" in m.group(1):
        found_model_import = True
        break
# Also check multiline version
if not found_model_import:
    ml_re = re.compile(
        r"from\s+radiology\.models\s+import\s*\((.*?)\)", re.DOTALL
    )
    for m in ml_re.finditer(v):
        if "RadiologyExam" in m.group(1):
            found_model_import = True
            break

if found_model_import:
    print("   ✓ radiology.models import includes RadiologyExam")
else:
    print("   ❌ radiology.models import is MISSING RadiologyExam — injecting now")

    # Strategy: insert a standalone import right after the first models import
    injected = False

    # Try to find "from radiology.models import RadiologyOrder"
    if "from radiology.models import RadiologyOrder" in v:
        v = v.replace(
            "from radiology.models import RadiologyOrder",
            "from radiology.models import RadiologyOrder\nfrom radiology.models import RadiologyExam",
            1,
        )
        injected = True
        print("   → injected 'from radiology.models import RadiologyExam' (after single-line RadiologyOrder import)")

    # Try to find a multiline "from radiology.models import ("
    elif "from radiology.models import (" in v:
        v = v.replace(
            "from radiology.models import (",
            "from radiology.models import (\n    RadiologyExam,",
            1,
        )
        injected = True
        print("   → injected 'RadiologyExam,' into multiline radiology.models import")

    # Last resort: insert right after "from patients.models import Patient"
    if not injected:
        if "from patients.models import Patient" in v:
            v = v.replace(
                "from patients.models import Patient",
                "from patients.models import Patient\nfrom radiology.models import RadiologyExam",
                1,
            )
            injected = True
            print("   → injected 'from radiology.models import RadiologyExam' (after patients.models)")

    # Absolute last resort: insert at the top, after the first "from " line
    if not injected:
        for i, line in enumerate(lines):
            if line.startswith("from ") and not line.startswith("from __future__"):
                lines.insert(i, "from radiology.models import RadiologyExam")
                v = "\n".join(lines)
                injected = True
                print(f"   → injected 'from radiology.models import RadiologyExam' at line {i+1}")
                break

    if not injected:
        print("   ❌ Could not find a safe insertion point. Dumping first 60 lines:")
        for i, line in enumerate(lines[:60], 1):
            print(f"   L{i:3}: {line}")
        sys.exit(1)

    vp.write_text(v, encoding="utf-8")

# ─── 3. Verify serializer import too ───────────────────────────────────
if "RadiologyExamSerializer" not in v.split("class RadiologyExamViewSet")[0]:
    print("   ❌ RadiologyExamSerializer also missing — injecting")
    if "from .serializers import (" in v:
        v = v.replace(
            "from .serializers import (",
            "from .serializers import (\n    RadiologyExamSerializer,",
            1,
        )
        vp.write_text(v, encoding="utf-8")
        print("   → injected RadiologyExamSerializer into serializers import")
else:
    print("   ✓ RadiologyExamSerializer is imported")

# ─── 4. Verify by running check ────────────────────────────────────────
print("\n==> manage.py check")
r = subprocess.run([str(PY), "manage.py", "check"], env=ENV, capture_output=True, text=True)
if r.returncode != 0:
    print("   ❌ check still failing. Top of traceback:")
    print(r.stderr.split("\n")[0] if r.stderr else "(no stderr)")
    print("\n   Full error tail:")
    for line in (r.stderr or r.stdout).splitlines()[-15:]:
        print("   " + line)
    sys.exit(1)
print("   " + (r.stdout.strip().splitlines()[-1] if r.stdout else "System check identified no issues (0 silenced)."))

# ─── 5. Run migrations ─────────────────────────────────────────────────
print("\n==> makemigrations radiology")
r = subprocess.run([str(PY), "manage.py", "makemigrations", "radiology"], env=ENV, capture_output=True, text=True)
print("   " + (r.stdout.strip() or "(no changes)").replace("\n", "\n   "))
if r.returncode != 0:
    print(r.stderr)
    sys.exit(1)

print("\n==> migrate")
subprocess.run([str(PY), "manage.py", "migrate"], check=True, env=ENV)

print("\n✅ All done. Push and redeploy both services.")