"""JWT authentication backend that also binds app.tenant_id in the DB session.

IMPORTANT: this module is named in DEFAULT_AUTHENTICATION_CLASSES and is
imported by DRF *while rest_framework.views is still loading*. Therefore it
must NOT import rest_framework.views / generics / schemas / routers (nor
anything that does, like rest_framework_simplejwt.views). Token-issuing views
live in api/tokens.py.
"""
from django.db import connection
from rest_framework_simplejwt.authentication import JWTAuthentication

from common.context import set_current_tenant


class TenantJWTAuthentication(JWTAuthentication):
    """Authenticate via JWT, then SET LOCAL app.tenant_id so RLS applies."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if getattr(user, "tenant_id", None):
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    [str(user.tenant_id)],
                )
            set_current_tenant(user.tenant)
        return user
