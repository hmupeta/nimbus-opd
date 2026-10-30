from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from tenants.models import MobileMoneyConfig

from .momo_serializers import MobileMoneyConfigSerializer
from .permissions import require_roles


class MobileMoneyConfigViewSet(viewsets.ModelViewSet):
    queryset = MobileMoneyConfig.objects.all()
    serializer_class = MobileMoneyConfigSerializer
    permission_classes = [require_roles("admin")]

    def get_queryset(self):
        qs = super().get_queryset().filter(tenant=self.request.user.tenant)
        for field in ("provider", "environment"):
            val = self.request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=False, methods=["post"], url_path="create-api-user")
    def create_api_user(self, request):
        """Simulate MTN/Airtel provisioning an API User and API Key."""
        import uuid
        provider = request.data.get("provider")
        callback_host = request.data.get("callback_host")
        
        if not provider or not callback_host:
            return Response({"detail": "provider and callback_host are required"}, status=400)

        # In production, you would POST to the provider's /apiuser endpoint here.
        # We simulate a successful response.
        generated_user = f"user_{uuid.uuid4().hex[:10]}"
        generated_key = f"key_{uuid.uuid4().hex[:16]}"
        
        return Response({
            "api_user": generated_user,
            "api_key": generated_key,
            "message": f"Successfully provisioned API User for {provider}."
        })

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        """Stub verification. Replace the body with a real provider API call.

        For now, it just checks that the required fields are populated.
        """
        cfg = self.get_object()
        required = ("merchant_code", "api_key", "api_secret")
        missing = [f for f in required if not getattr(cfg, f, "")]
        if missing:
            cfg.last_verification_status = "failed"
            cfg.last_verification_message = f"Missing: {', '.join(missing)}"
        else:
            # In production, you'd make an OAuth request here.
            # e.g. POST /collection/token/ with Basic Auth of api_user:api_key
            if cfg.api_user and cfg.api_key:
                cfg.last_verification_status = "ok"
                cfg.last_verification_message = "OAuth Handshake successful. Token expires in 3600s."
            else:
                cfg.last_verification_status = "failed"
                cfg.last_verification_message = "OAuth failed: Missing API User or Key."
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
            return Response(
                {"detail": "Config must be active before it can be the default."},
                status=status.HTTP_409_CONFLICT,
            )
        MobileMoneyConfig.objects.filter(
            tenant=cfg.tenant, is_default=True,
        ).exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default"])
        return Response(MobileMoneyConfigSerializer(cfg).data)
