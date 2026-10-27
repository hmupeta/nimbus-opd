from rest_framework.permissions import BasePermission


def require_roles(*roles):
    """Return a permission class that allows only these roles (or superuser)."""
    allowed = set(roles)

    class _HasRole(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(
                u and u.is_authenticated
                and (u.is_superuser or u.role in allowed)
            )

    _HasRole.__name__ = f"Role_{'_'.join(sorted(allowed))}"
    return _HasRole


class TenantHeaderMatch(BasePermission):
    """If X-Tenant-ID is present, it must match the authenticated user's tenant."""

    def has_permission(self, request, view):
        header = request.headers.get("X-Tenant-ID")
        if not header:
            return True
        u = request.user
        return bool(u and u.is_authenticated and str(u.tenant_id) == header)
