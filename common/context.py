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
