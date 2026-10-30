from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from accounting.models import ChartOfAccount, Supplier, Bill, Expense, FixedAsset
from api.serializers import ChartOfAccountSerializer, SupplierSerializer, BillSerializer, ExpenseSerializer, FixedAssetSerializer
from api.permissions import require_roles
from api.views import TenantScopedViewSet

FINANCE_ROLES = ["admin", "accountant", "finance_manager"]

class ChartOfAccountViewSet(TenantScopedViewSet):
    serializer_class = ChartOfAccountSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return ChartOfAccount.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("code")

class SupplierViewSet(TenantScopedViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return Supplier.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("name")

class BillViewSet(TenantScopedViewSet):
    serializer_class = BillSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return Bill.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-date")

class ExpenseViewSet(TenantScopedViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return Expense.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-date")
    
    @action(detail=True, methods=["post"], permission_classes=[require_roles("admin", "finance_manager")])
    def approve(self, request, pk=None):
        exp = self.get_object()
        exp.is_approved = True
        exp.save()
        return Response({"status": "approved"})

class FixedAssetViewSet(TenantScopedViewSet):
    serializer_class = FixedAssetSerializer
    permission_classes = [require_roles(*FINANCE_ROLES)]
    def get_queryset(self):
        return FixedAsset.all_objects.filter(tenant_id=self.request.user.tenant_id).order_by("-purchase_date")
