#!/usr/bin/env python3
"""
fix_lab_serializer_order.py -- Move LabResultSerializer above LabOrderSerializer.
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

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

sp = ROOT / "api" / "serializers.py"
s = sp.read_text(encoding="utf-8")

# ─── 1. Extract LabResultSerializer ────────────────────────────────────
match = re.search(r"class LabResultSerializer\(serializers\.ModelSerializer\):.*?(?=\nclass |\Z)", s, re.DOTALL)
if not match:
    sys.exit("Could not find LabResultSerializer")

result_serializer_code = match.group(0)
s_without_result = s.replace(result_serializer_code, "").strip() + "\n"

# ─── 2. Re-insert it above LabOrderSerializer ──────────────────────────
target = "class LabOrderSerializer(serializers.ModelSerializer):"
if target not in s_without_result:
    sys.exit("Could not find LabOrderSerializer target")

new_s = s_without_result.replace(
    target, 
    result_serializer_code + "\n\n" + target
)

sp.write_text(new_s, encoding="utf-8")
print("   reordered api/serializers.py")

print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Done. You can restart the server now.")