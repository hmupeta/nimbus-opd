from datetime import timedelta
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets

from visits.models import Visit
from billing.models import Payment, InvoiceItem
from audit.models import AuditLog
from api.permissions import require_roles
from api.serializers import AuditLogSerializer


class AnalyticsTrendView(APIView):
    permission_classes = [require_roles("admin", "doctor")]
    
    def get(self, request):
        today = timezone.now().date()
        start_date = today - timedelta(days=6)
        
        # 1. Footfall (Last 7 days)
        footfall_qs = Visit.objects.filter(arrived_at__date__gte=start_date) \
            .annotate(date=TruncDate('arrived_at')) \
            .values('date') \
            .annotate(count=Count('id')) \
            .order_by('date')
            
        footfall_dict = {str(item['date']): item['count'] for item in footfall_qs}
        
        # 2. Revenue Trend (Last 7 days)
        revenue_qs = Payment.objects.filter(paid_at__date__gte=start_date) \
            .annotate(date=TruncDate('paid_at')) \
            .values('date') \
            .annotate(total=Sum('amount')) \
            .order_by('date')
            
        revenue_dict = {str(item['date']): float(item['total']) for item in revenue_qs}
        
        # 3. Revenue by Category
        category_qs = InvoiceItem.objects.values('category') \
            .annotate(total=Sum('total')) \
            .order_by('-total')
            
        # Format for charts
        chart_data = []
        for i in range(7):
            d = start_date + timedelta(days=i)
            d_str = str(d)
            chart_data.append({
                "date": d.strftime("%a"), # Mon, Tue, etc.
                "visits": footfall_dict.get(d_str, 0),
                "revenue": revenue_dict.get(d_str, 0.0)
            })
            
        pie_data = [{"name": item["category"].capitalize(), "value": float(item["total"])} for item in category_qs]

        return Response({
            "trend": chart_data,
            "category_breakdown": pie_data
        })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [require_roles("admin")]
    
    def get_queryset(self):
        return AuditLog.objects.all().order_by("-at")[:200] # Last 200 actions


class ZReportView(APIView):
    permission_classes = [require_roles("admin", "receptionist")]
    
    def get(self, request):
        today = timezone.now().date()
        # Payments received by THIS user today
        payments = Payment.objects.filter(received_by=request.user, paid_at__date=today)
        
        summary = payments.values('method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        total = payments.aggregate(total=Sum('amount'))['total'] or 0.00
        
        return Response({
            "date": today,
            "cashier": request.user.get_full_name() or request.user.email,
            "summary": list(summary),
            "total_collected": total
        })
