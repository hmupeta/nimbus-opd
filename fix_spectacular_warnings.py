#!/usr/bin/env python3
"""
fix_spectacular_warnings.py

1. Registers an OpenApiAuthenticationExtension for TenantJWTAuthentication
   (silences the "could not resolve authenticator" warnings).
2. Adds explicit response schemas to the four report APIViews
   (silences the "unable to guess serializer" errors and gives Swagger real
   response shapes for the dashboard / revenue / insurance / AR aging endpoints).
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


# ─── 1. OpenApiAuthenticationExtension ─────────────────────────────────
write("api/schema_extensions.py", '''\
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class TenantJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tell drf-spectacular that TenantJWTAuthentication uses HTTP bearer + JWT.

    The scheme *name* here ('jwtAuth') must match the securityScheme key used
    in SPECTACULAR_SETTINGS['APPEND_COMPONENTS'] and SPECTACULAR_SETTINGS['SECURITY'].
    """

    target_class = "api.auth.TenantJWTAuthentication"
    name = "jwtAuth"
    match_subclasses = True

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
''')

# ─── 2. Ensure ready() imports the extension module ────────────────────
write("api/apps.py", '''\
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Registers the OpenApiAuthenticationExtension for TenantJWTAuthentication
        from . import schema_extensions  # noqa: F401
''')

# ─── 3. Rewrite report_views.py with explicit response schemas ─────────
write("api/report_views.py", '''\
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice, InvoiceItem, Payment
from visits.models import Visit

from .permissions import require_roles


# ── Response schemas (used only for Swagger docs) ──────────────────────
DashboardCensus = inline_serializer(
    name="DashboardCensus",
    fields={
        "total":           serializers.IntegerField(),
        "waiting":         serializers.IntegerField(),
        "triaged":         serializers.IntegerField(),
        "in_consultation": serializers.IntegerField(),
        "closed":          serializers.IntegerField(),
    },
)

DashboardRevenue = inline_serializer(
    name="DashboardRevenue",
    fields={
        "today":      serializers.DecimalField(max_digits=12, decimal_places=2),
        "this_month": serializers.DecimalField(max_digits=12, decimal_places=2),
    },
)

DashboardResponse = inline_serializer(
    name="DashboardResponse",
    fields={
        "date":    serializers.DateField(),
        "census":  DashboardCensus,
        "revenue": DashboardRevenue,
    },
)

RevenueBreakdownItem = inline_serializer(
    name="RevenueBreakdownItem",
    fields={
        "category": serializers.CharField(),
        "count":    serializers.IntegerField(),
        "total":    serializers.DecimalField(max_digits=12, decimal_places=2),
    },
)

RevenueByCategoryResponse = inline_serializer(
    name="RevenueByCategoryResponse",
    fields={
        "breakdown":     RevenueBreakdownItem(many=True),
        "total_revenue": serializers.DecimalField(max_digits=12, decimal_places=2),
    },
)

InsuranceMixItem = inline_serializer(
    name="InsuranceMixItem",
    fields={
        "method": serializers.CharField(),
        "count":  serializers.IntegerField(),
        "total":  serializers.DecimalField(max_digits=12, decimal_places=2),
    },
)

InsuranceMixResponse = inline_serializer(
    name="InsuranceMixResponse",
    fields={
        "payment_methods":  InsuranceMixItem(many=True),
        "total_collected":  serializers.DecimalField(max_digits=12, decimal_places=2),
    },
)

ARAgingBuckets = inline_serializer(
    name="ARAgingBuckets",
    fields={
        "0_30_days":    serializers.DecimalField(max_digits=12, decimal_places=2),
        "31_60_days":   serializers.DecimalField(max_digits=12, decimal_places=2),
        "61_90_days":   serializers.DecimalField(max_digits=12, decimal_places=2),
        "90_plus_days": serializers.DecimalField(max_digits=12, decimal_places=2),
    },
)

ARAgingResponse = inline_serializer(
    name="ARAgingResponse",
    fields={
        "total_outstanding": serializers.DecimalField(max_digits=12, decimal_places=2),
        "buckets":           ARAgingBuckets,
    },
)


# ── Views ──────────────────────────────────────────────────────────────
class DashboardSummaryView(APIView):
    permission_classes = [require_roles("admin", "doctor")]

    @extend_schema(responses=DashboardResponse)
    def get(self, request):
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        visits_today = Visit.objects.filter(arrived_at__date=today)
        census = visits_today.aggregate(
            total=Count("id"),
            waiting=Count("id", filter=Q(status=Visit.Status.OPEN)),
            triaged=Count("id", filter=Q(status=Visit.Status.TRIAGED)),
            in_consultation=Count("id", filter=Q(status=Visit.Status.IN_CONSULTATION)),
            closed=Count("id", filter=Q(status=Visit.Status.CLOSED)),
        )

        revenue_today = Payment.objects.filter(
            paid_at__date=today
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        revenue_month = Payment.objects.filter(
            paid_at__date__gte=start_of_month
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        return Response({
            "date": today,
            "census": census,
            "revenue": {
                "today": revenue_today,
                "this_month": revenue_month,
            },
        })


class RevenueByCategoryView(APIView):
    permission_classes = [require_roles("admin")]

    @extend_schema(responses=RevenueByCategoryResponse)
    def get(self, request):
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")

        qs = InvoiceItem.objects.all()
        if start_date:
            qs = qs.filter(invoice__created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice__created_at__date__lte=end_date)

        breakdown = list(
            qs.values("category").annotate(
                total=Sum("total"),
                count=Count("id"),
            ).order_by("-total")
        )

        return Response({
            "breakdown": breakdown,
            "total_revenue": sum(item["total"] for item in breakdown),
        })


class InsuranceMixView(APIView):
    permission_classes = [require_roles("admin")]

    @extend_schema(responses=InsuranceMixResponse)
    def get(self, request):
        payments = list(
            Payment.objects.values("method").annotate(
                total=Sum("amount"),
                count=Count("id"),
            ).order_by("-total")
        )

        return Response({
            "payment_methods": payments,
            "total_collected": sum(p["total"] for p in payments),
        })


class ARAgingView(APIView):
    """Accounts Receivable Aging: how much money is owed, and how old is it?"""
    permission_classes = [require_roles("admin")]

    @extend_schema(responses=ARAgingResponse)
    def get(self, request):
        today = timezone.now().date()

        unpaid_invoices = Invoice.objects.filter(
            balance__gt=0,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PART_PAID],
        )

        buckets = {
            "0_30_days":    Decimal("0.00"),
            "31_60_days":   Decimal("0.00"),
            "61_90_days":   Decimal("0.00"),
            "90_plus_days": Decimal("0.00"),
        }

        for inv in unpaid_invoices:
            ref_date = inv.issued_at.date() if inv.issued_at else inv.created_at.date()
            age = (today - ref_date).days

            if age <= 30:
                buckets["0_30_days"] += inv.balance
            elif age <= 60:
                buckets["31_60_days"] += inv.balance
            elif age <= 90:
                buckets["61_90_days"] += inv.balance
            else:
                buckets["90_plus_days"] += inv.balance

        return Response({
            "total_outstanding": sum(buckets.values()),
            "buckets": buckets,
        })
''')

# ─── 4. Register the extension via INSTALLED_APPS (use explicit config) ─
print("==> Patching config/settings.py (use api.apps.ApiConfig)")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if '"api.apps.ApiConfig"' not in s and '"api",' in s:
    s = s.replace('"api",', '"api.apps.ApiConfig",')
    sp.write_text(s, encoding="utf-8")
    print("   patched config/settings.py")
else:
    print("   config/settings.py already uses api.apps.ApiConfig (or no change)")

# ─── 5. Sanity check ───────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print("==> Verifying schema generation (should show 0 warnings below)")
sh(PY, "manage.py", "spectacular", "--file", "-")

print()
print("==> Done. Restart the server and reload /api/docs/")