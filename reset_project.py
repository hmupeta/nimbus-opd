#!/usr/bin/env python3
"""
reset_project.py -- Nuke the DB and rebuild from scratch.
Use --drop to completely drop and recreate the PostgreSQL database.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def main():
    if "--drop" in sys.argv:
        print("==> Dropping and recreating database 'opd'...")
        # Connect to 'postgres' db to drop 'opd'
        env_drop = ENV.copy()
        env_drop["DB_NAME"] = "postgres"
        sql = f"DROP DATABASE IF EXISTS {ENV['DB_NAME']}; CREATE DATABASE {ENV['DB_NAME']} OWNER {ENV['DB_USER']};"
        subprocess.run(
            ["psql", "-U", ENV["DB_USER"], "-d", "postgres", "-c", sql],
            env=env_drop, check=True
        )
    else:
        print("==> Flushing database (truncating all tables)...")
        sh(PY, "manage.py", "flush", "--no-input")

    print("==> Applying migrations...")
    sh(PY, "manage.py", "migrate")

    print("==> Seeding demo data...")
    sh(PY, "manage.py", "seed_demo", "--reset")

    print("==> Done! Run 'python manage.py runserver' to start.")

if __name__ == "__main__":
    main()
