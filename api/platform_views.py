from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from tenants.models import Tenant, User
from api.serializers import TenantSerializer


class PlatformPermission(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, "is_platform_admin", False)


class PlatformStatsView(APIView):
    permission_classes = [PlatformPermission]

    def get(self, request):
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()
        pending_tenants = Tenant.objects.filter(is_active=False).count()
        
        # Mock MRR calculation: Assume all active tenants are on the Pro plan (K3,500/mo)
        mrr = active_tenants * 3500

        return Response({
            "total_clinics": total_tenants,
            "active_clinics": active_tenants,
            "pending_clinics": pending_tenants,
            "mrr_zmw": mrr,
        })


class PlatformTenantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tenant.objects.all().order_by("-created_at")
    serializer_class = TenantSerializer
    permission_classes = [PlatformPermission]


    def list(self, request, *args, **kwargs):
        from django.utils.dateparse import parse_datetime
        from datetime import timedelta

        response = super().list(request, *args, **kwargs)
        
        # Handle Pagination correctly
        if isinstance(response.data, dict) and "results" in response.data:
            clinics = response.data["results"]
        else:
            clinics = response.data

        for clinic in clinics:
            if clinic.get("is_active"):
                clinic["billing_status"] = "paid"
                clinic["plan"] = "Pro (K3,500/mo)"
                # Calculate next billing date safely
                created_str = clinic.get("created_at")
                if created_str:
                    created = parse_datetime(created_str)
                    clinic["next_billing"] = (created + timedelta(days=30)).strftime("%Y-%m-%d") if created else "N/A"
                else:
                    clinic["next_billing"] = "N/A"
            else:
                clinic["billing_status"] = "pending"
                clinic["plan"] = "Starter (K1,250/mo)"
                clinic["next_billing"] = "Awaiting Payment"

        return response

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = True
        tenant.save(update_fields=["is_active"])
        return Response({"detail": "Clinic approved and activated successfully."})

    @action(detail=True, methods=["post"])
    def impersonate(self, request, pk=None):
        tenant = self.get_object()
        # Find the primary admin for this tenant
        admin = User.objects.filter(tenant=tenant, role="admin").first()
        if not admin:
            return Response({"detail": "No admin user found for this clinic."}, status=status.HTTP_404_NOT_FOUND)

        # Generate tokens manually
        refresh = RefreshToken.for_user(admin)
        # Inject custom claims exactly like our custom serializer does
        refresh["tenant_id"] = str(admin.tenant_id)
        refresh["role"] = admin.role
        refresh["email"] = admin.email
        refresh["full_name"] = admin.get_full_name() or admin.email
        refresh["is_platform_admin"] = False # Impersonated session is not platform admin

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "clinic_name": tenant.name
        })
