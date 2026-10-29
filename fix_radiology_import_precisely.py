#!/usr/bin/env python3
"""
fix_radiology_import_precisely.py -- Force-add RadiologyExam to imports.
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

# 1. Add model import if missing (check specifically for the import statement)
if "from radiology.models import RadiologyExam" not in v and "from radiology.models import (" not in v:
    if "from radiology.models import RadiologyOrder" in v:
        v = v.replace(
            "from radiology.models import RadiologyOrder",
            "from radiology.models import RadiologyExam, RadiologyOrder"
        )
        print("   patched: added RadiologyExam to radiology.models import")
    elif "from radiology.models import" in v:
        # Multi-line import block
        v = v.replace(
            "from radiology.models import (",
            "from radiology.models import (\n    RadiologyExam,\n    RadiologyOrder,"
        )
        # Remove duplicate RadiologyOrder if it was already in the list
        v = v.replace("    RadiologyOrder,\n    RadiologyExam,\n    RadiologyOrder,", "    RadiologyExam,\n    RadiologyOrder,")
        print("   patched: added RadiologyExam to multiline import")
    else:
        # No radiology import at all — add one
        v = v.replace(
            "from patients.models import Patient",
            "from patients.models import Patient\nfrom radiology.models import RadiologyExam, RadiologyOrder"
        )
        print("   patched: created new radiology.models import")
else:
    print("   radiology model import already present")

# 2. Add serializer import if missing
if "RadiologyExamSerializer" not in v.split("class RadiologyExamViewSet")[0]:
    # Add to the serializers import block
    if "from .serializers import (" in v:
        v = v.replace(
            "from .serializers import (\n    InvoiceSerializer,",
            "from .serializers import (\n    InvoiceSerializer,\n    RadiologyExamSerializer,"
        )
        if "RadiologyExamSerializer" not in v:
            # Different serializers block layout — insert after another known item
            v = v.replace(
                "    RadiologyOrderSerializer,",
                "    RadiologyExamSerializer,\n    RadiologyOrderSerializer,"
            )
    print("   patched: added RadiologyExamSerializer import")

vp.write_text(v, encoding="utf-8")

# 3. Verify import explicitly
v2 = vp.read_text(encoding="utf-8")
if "RadiologyExam" not in v2.split("class RadiologyExamViewSet")[0]:
    print("   ❌ FAILED: RadiologyExam still not imported before class")
    # Print the top 60 lines so we can see what's there
    print("\n--- First 60 lines of api/views.py ---")
    for i, line in enumerate(v2.splitlines()[:60], 1):
        print(f"{i:3} {line}")
    print("---")
    sys.exit(1)

print("   ✓ RadiologyExam import confirmed")

# 4. Run migrations
print("==> manage.py check")
r = subprocess.run([str(PY), "manage.py", "check"], env=ENV, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stdout)
    print(r.stderr)
    sys.exit(1)
print("   " + (r.stdout.strip().splitlines()[-1] if r.stdout else "OK"))

print("==> makemigrations radiology")
subprocess.run([str(PY), "manage.py", "makemigrations", "radiology"], check=True, env=ENV)

print("==> migrate")
subprocess.run([str(PY), "manage.py", "migrate"], check=True, env=ENV)

print("\n✅ Done. Push and redeploy both services.")