from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from tenants.models import PaymentGatewayConfig
from .gateway_serializers import PaymentGatewayConfigSerializer
from .permissions import require_roles


class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):
    queryset = PaymentGatewayConfig.objects.all()
    serializer_class = PaymentGatewayConfigSerializer
    permission_classes = [require_roles("admin")]

    def get_queryset(self):
        qs = super().get_queryset().filter(tenant=self.request.user.tenant)
        for field in ("provider", "environment"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        cfg = self.get_object()
        missing = []
        if not cfg.publishable_key: missing.append("publishable_key")
        if not cfg.secret_key: missing.append("secret_key")

        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing: {', '.join(missing)}"
        else:
            cfg.last_verification_status = "ok"
            cfg.last_verification_message = "Credentials present. (Gateway API not yet wired.)"
            
        cfg.last_verified_at = timezone.now()
        cfg.save(update_fields=["last_verified_at", "last_verification_status", "last_verification_message"])
        return Response(PaymentGatewayConfigSerializer(cfg).data)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        cfg = self.get_object()
        if not cfg.is_active:
            return Response({"detail": "Config must be active to be default."}, status=status.HTTP_409_CONFLICT)
        PaymentGatewayConfig.objects.filter(tenant=cfg.tenant, is_default=True).exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default"])
        return Response(PaymentGatewayConfigSerializer(cfg).data)
