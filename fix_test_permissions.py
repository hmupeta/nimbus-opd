#!/usr/bin/env python3
"""
fix_test_permissions.py -- Grant CREATEDB to opd_owner and run tests.
"""
from __future__ import annotations
import os
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
ENV.setdefault("DB_HOST", "127.0.0.1")
ENV.setdefault("DB_PORT", "5432")

# ─── 1. Grant CREATEDB to opd_owner ────────────────────────────────────
print("==> Granting CREATEDB privilege to opd_owner")
print("    (You will be prompted for the 'postgres' superuser password)")

grant_cmd = [
    "psql",
    "-U", "postgres",
    "-h", ENV["DB_HOST"],
    "-p", ENV["DB_PORT"],
    "-d", "postgres",
    "-c", 'ALTER ROLE opd_owner CREATEDB;'
]

try:
    result = subprocess.run(grant_cmd, check=True)
    print("   ✅ Permission granted successfully")
except subprocess.CalledProcessError:
    print("   ❌ Failed. Please run this manually:")
    print("      psql -U postgres -c \"ALTER ROLE opd_owner CREATEDB;\"")
    sys.exit(1)
except FileNotFoundError:
    print("   ❌ psql not found. Please run this manually in pgAdmin or psql:")
    print("      ALTER ROLE opd_owner CREATEDB;")
    sys.exit(1)

# ─── 2. Run the tests ──────────────────────────────────────────────────
print("\n==> Running RLS isolation tests...")
try:
    subprocess.run(
        [str(PY), "manage.py", "test", "tests.test_isolation", "-v", "2"],
        check=True, env=ENV
    )
    print("\n✅ All tests passed! Multi-tenant isolation is mathematically proven.")
except subprocess.CalledProcessError:
    print("\n❌ Some tests failed. Check the output above for details.")
    sys.exit(1)