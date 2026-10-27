from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice, InvoiceItem, Payment
from visits.models import Visit

from .permissions import require_roles


# ─── Response schemas (real Serializer classes → nesting works) ────────
class DashboardCensusSerializer(serializers.Serializer):
    total           = serializers.IntegerField()
    waiting         = serializers.IntegerField()
    triaged         = serializers.IntegerField()
    in_consultation = serializers.IntegerField()
    closed          = serializers.IntegerField()


class DashboardRevenueSerializer(serializers.Serializer):
    today      = serializers.DecimalField(max_digits=12, decimal_places=2)
    this_month = serializers.DecimalField(max_digits=12, decimal_places=2)


class DashboardResponseSerializer(serializers.Serializer):
    date    = serializers.DateField()
    census  = DashboardCensusSerializer()
    revenue = DashboardRevenueSerializer()


class RevenueBreakdownItemSerializer(serializers.Serializer):
    category = serializers.CharField()
    count    = serializers.IntegerField()
    total    = serializers.DecimalField(max_digits=12, decimal_places=2)


class RevenueByCategoryResponseSerializer(serializers.Serializer):
    breakdown     = RevenueBreakdownItemSerializer(many=True)
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)


class InsuranceMixItemSerializer(serializers.Serializer):
    method = serializers.CharField()
    count  = serializers.IntegerField()
    total  = serializers.DecimalField(max_digits=12, decimal_places=2)


class InsuranceMixResponseSerializer(serializers.Serializer):
    payment_methods = InsuranceMixItemSerializer(many=True)
    total_collected = serializers.DecimalField(max_digits=12, decimal_places=2)


class ARAgingBucketsSerializer(serializers.Serializer):
    bucket_0_30    = serializers.DecimalField(
        max_digits=12, decimal_places=2, source="0_30_days")
    bucket_31_60   = serializers.DecimalField(
        max_digits=12, decimal_places=2, source="31_60_days")
    bucket_61_90   = serializers.DecimalField(
        max_digits=12, decimal_places=2, source="61_90_days")
    bucket_90_plus = serializers.DecimalField(
        max_digits=12, decimal_places=2, source="90_plus_days")


class ARAgingResponseSerializer(serializers.Serializer):
    total_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)
    buckets           = ARAgingBucketsSerializer()


# ─── Views ─────────────────────────────────────────────────────────────
class DashboardSummaryView(APIView):
    permission_classes = [require_roles("admin", "doctor")]

    @extend_schema(responses=DashboardResponseSerializer)
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

    @extend_schema(responses=RevenueByCategoryResponseSerializer)
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

    @extend_schema(responses=InsuranceMixResponseSerializer)
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

    @extend_schema(responses=ARAgingResponseSerializer)
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
