#!/usr/bin/env python3
"""
extend_reports.py -- Add reporting and analytics endpoints.
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


# ─── 1. Write reporting views ──────────────────────────────────────────
write("api/report_views.py", '''\
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice, InvoiceItem, Payment
from patients.models import Patient
from visits.models import Visit

from .permissions import require_roles


class DashboardSummaryView(APIView):
    permission_classes = [require_roles("admin", "doctor")]

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

        # Revenue is based on successful payments captured in the DB
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
            }
        })


class RevenueByCategoryView(APIView):
    permission_classes = [require_roles("admin")]

    def get(self, request):
        start_date = request.query_params.get("start")
        end_date = request.query_params.get("end")

        qs = InvoiceItem.objects.all()
        if start_date:
            qs = qs.filter(invoice__created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice__created_at__date__lte=end_date)

        # Group by category and sum the totals
        breakdown = qs.values("category").annotate(
            total=Sum("total"),
            count=Count("id")
        ).order_by("-total")

        return Response({
            "breakdown": list(breakdown),
            "total_revenue": sum(item["total"] for item in breakdown)
        })


class InsuranceMixView(APIView):
    permission_classes = [require_roles("admin")]

    def get(self, request):
        # How much was paid via cash/card/momo vs insurance claims
        payments = Payment.objects.values("method").annotate(
            total=Sum("amount"),
            count=Count("id")
        ).order_by("-total")

        return Response({
            "payment_methods": list(payments),
            "total_collected": sum(p["total"] for p in payments)
        })


class ARAgingView(APIView):
    """Accounts Receivable Aging: How much money is owed, and how old is it?"""
    permission_classes = [require_roles("admin")]

    def get(self, request):
        today = timezone.now().date()

        unpaid_invoices = Invoice.objects.filter(
            balance__gt=0,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PART_PAID]
        )

        buckets = {
            "0_30_days": Decimal("0.00"),
            "31_60_days": Decimal("0.00"),
            "61_90_days": Decimal("0.00"),
            "90_plus_days": Decimal("0.00"),
        }

        for inv in unpaid_invoices:
            # Fallback to created_at if issued_at is null
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
            "buckets": buckets
        })
''')

# ─── 2. Register routes ────────────────────────────────────────────────
print("==> Patching api/urls.py")
up = ROOT / "api" / "urls.py"
u = up.read_text(encoding="utf-8")

if "report_views" not in u:
    u = u.replace(
        "from django.urls import include, path",
        "from django.urls import include, path\n"
        "from .report_views import (\n"
        "    DashboardSummaryView, RevenueByCategoryView,\n"
        "    InsuranceMixView, ARAgingView\n"
        ")"
    )
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('reports/dashboard/', DashboardSummaryView.as_view(), name='report-dashboard'),\n"
        "    path('reports/revenue-by-category/', RevenueByCategoryView.as_view(), name='report-revenue'),\n"
        "    path('reports/insurance-mix/', InsuranceMixView.as_view(), name='report-insurance'),\n"
        "    path('reports/ar-aging/', ARAgingView.as_view(), name='report-ar-aging'),"
    )
    up.write_text(u, encoding="utf-8")
    print("   patched api/urls.py")

# ─── 3. Sanity check ───────────────────────────────────────────────────
print("==> manage.py check")
sh(PY, "manage.py", "check")

print()
print("==> Done.")