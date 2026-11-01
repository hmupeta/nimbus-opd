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

        # Create an unsaved temp config to use the MTN Service
        from tenants.models import MobileMoneyConfig
        temp_cfg = MobileMoneyConfig(
            tenant=request.user.tenant,
            provider=provider,
            environment="sandbox",
            subscription_key=subscription_key
        )
        
        try:
            service = MTNMoMoService(temp_cfg)
            # This now actually hits MTN to get a real UUID and API Key
            api_user, api_key = service.provision_api_user(callback_host, subscription_key)
            return Response({
                "api_user": api_user,
                "api_key": api_key,
                "message": "Successfully provisioned a real UUID and API Key from MTN Sandbox."
            })
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        cfg = self.get_object()
        
        required = ("merchant_code", "api_user", "api_key", "api_secret", "subscription_key")
        missing = [f for f in required if not getattr(cfg, f, "")]
        
        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing fields: {', '.join(missing)}"
        else:
            try:
                service = MTNMoMoService(cfg)
                service._get_token()
                cfg.last_verification_status = "ok"
                cfg.last_verification_message = "OAuth Handshake successful."
            except Exception as e:
                cfg.last_verification_status = "failed"
                cfg.last_verification_message = str(e)
                
        cfg.last_verified_at = timezone.now()
        cfg.save(update_fields=[
            "last_verified_at", "last_verification_status",
            "last_verification_message",
        ])
        return Response(MobileMoneyConfigSerializer(cfg).data)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        cfg = self.get_object()
        if not cfg.is_active:
            return Response({"detail": "Config must be active."}, status=400)
        MobileMoneyConfig.objects.filter(tenant=cfg.tenant, is_default=True).exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default"])
        return Response(MobileMoneyConfigSerializer(cfg).data)