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
            cfg.last_verification_status = "ok"
            cfg.last_verification_message = (
                "All required fields present. "
                "(Provider API not yet wired.)"
            )
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
