from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from tenants.models import MobileMoneyConfig
from api.momo_serializers import MobileMoneyConfigSerializer
from api.permissions import require_roles
from billing.mtn_service import MTNMoMoService


class MobileMoneyConfigViewSet(viewsets.ModelViewSet):
    queryset = MobileMoneyConfig.objects.all()
    serializer_class = MobileMoneyConfigSerializer
    permission_classes = [require_roles("admin", "finance_manager")]

    def get_queryset(self):
        qs = super().get_queryset().filter(tenant=self.request.user.tenant)
        for field in ("provider", "environment"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=False, methods=["post"], url_path="create-api-user")
    def create_api_user(self, request):
        provider = request.data.get("provider")
        callback_host = request.data.get("callback_host")
        subscription_key = request.data.get("subscription_key")
        
        if not provider or not callback_host or not subscription_key:
            return Response({"detail": "provider, callback_host, and subscription_key are required"}, status=400)

        temp_cfg = MobileMoneyConfig(
            tenant=request.user.tenant,
            provider=provider,
            environment="sandbox",
            subscription_key=subscription_key
        )
        
        try:
            service = MTNMoMoService(temp_cfg)
            api_user, api_key = service.provision_api_user(callback_host, subscription_key)
            return Response({
                "api_user": api_user,
                "api_key": api_key,
                "message": "Successfully provisioned a real UUID and API Key from MTN Sandbox."
            })
        except Exception as e:
            return Response({"detail": str(e)}, status=400)