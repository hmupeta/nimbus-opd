#!/usr/bin/env python3
"""
fix_contextvar_reset.py -- use ContextVar tokens to safely nest db_tenant_context.
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


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ─── 1. Rewrite common/context.py ──────────────────────────────────────
write("common/context.py", '''\
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import connection, transaction

_current_tenant = ContextVar("current_tenant", default=None)
_current_user = ContextVar("current_user", default=None)
_current_ip = ContextVar("current_ip", default=None)
_audit_suspended = ContextVar("audit_suspended", default=False)


def set_current_tenant(tenant):
    _current_tenant.set(tenant)


def get_current_tenant():
    return _current_tenant.get()


def clear_current_tenant():
    _current_tenant.set(None)


def set_current_user(user):
    _current_user.set(user)


def get_current_user():
    return _current_user.get()


def set_current_ip(ip):
    _current_ip.set(ip)


def get_current_ip():
    return _current_ip.get()


def is_audit_suspended() -> bool:
    return _audit_suspended.get()


@contextmanager
def suspend_audit():
    """Temporarily disable audit signal logging (used during data resets)."""
    token = _audit_suspended.set(True)
    try:
        yield
    finally:
        _audit_suspended.reset(token)


@contextmanager
def db_tenant_context(tenant):
    """Bind the tenant in memory AND in the DB session (transaction-scoped)."""
    token = _current_tenant.set(tenant)
    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    [str(tenant.id)],
                )
            yield
    finally:
        # Restore the previous tenant, rather than blindly setting it to None.
        # This allows db_tenant_context to be safely nested.
        _current_tenant.reset(token)
''')

# ─── 2. Re-run seed_demo with NO_REDIS=1 ───────────────────────────────
print("==> seed_demo --reset (NO_REDIS=1)")
seed_env = ENV.copy()
seed_env["NO_REDIS"] = "1"
subprocess.run([str(PY), "manage.py", "seed_demo", "--reset"], check=True, env=seed_env)

print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")