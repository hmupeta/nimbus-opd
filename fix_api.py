#!/usr/bin/env python3
"""
fix_api.py -- resolve the DRF circular import by splitting api/auth.py
              into (auth backend) + (token-issuing view).
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


# ─── 1. api/auth.py: ONLY the auth backend, no views ───────────────────
write("api/auth.py", '''\
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
''')

# ─── 2. api/tokens.py: token-issuing views ─────────────────────────────
write("api/tokens.py", '''\
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.get_full_name() or user.email
        return token


class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer
''')

# ─── 3. api/urls.py: import the view from .tokens ──────────────────────
write("api/urls.py", '''\
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .tokens import TenantTokenObtainPairView
from .views import (
    ClinicalNoteViewSet, LabOrderViewSet, LabResultViewSet, LabTestViewSet,
    MedicineViewSet, OrderItemViewSet, OrderViewSet, PatientViewSet,
    PharmacyItemViewSet, PharmacyOrderViewSet, RadiologyOrderViewSet,
    StockMovementViewSet, StockViewSet, TenantViewSet, UserViewSet,
    VisitViewSet, VitalsViewSet, VitalDefinitionViewSet, VitalValueViewSet,
)

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("users", UserViewSet, basename="user")
router.register("patients", PatientViewSet, basename="patient")
router.register("visits", VisitViewSet, basename="visit")
router.register("vitals", VitalsViewSet, basename="vitals")
router.register("vital-definitions", VitalDefinitionViewSet, basename="vital-def")
router.register("vital-values", VitalValueViewSet, basename="vital-value")
router.register("notes", ClinicalNoteViewSet, basename="note")
router.register("orders", OrderViewSet, basename="order")
router.register("order-items", OrderItemViewSet, basename="order-item")
router.register("lab-tests", LabTestViewSet, basename="lab-test")
router.register("lab-orders", LabOrderViewSet, basename="lab-order")
router.register("lab-results", LabResultViewSet, basename="lab-result")
router.register("radiology-orders", RadiologyOrderViewSet, basename="rad-order")
router.register("medicines", MedicineViewSet, basename="medicine")
router.register("pharmacy-orders", PharmacyOrderViewSet, basename="pharm-order")
router.register("pharmacy-items", PharmacyItemViewSet, basename="pharm-item")
router.register("stock", StockViewSet, basename="stock")
router.register("stock-movements", StockMovementViewSet, basename="stock-mv")

urlpatterns = [
    path("auth/login/", TenantTokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("", include(router.urls)),
]
''')

# ─── 4. sanity check ───────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done. Start the server with the app role:")
print("   $env:DB_USER='opd_app'; $env:DB_PASSWORD='opd_app'")
print("   python manage.py runserver")