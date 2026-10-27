from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import serializers


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Block login if the tenant is not active (pending approval/payment)
        if self.user.tenant and not self.user.tenant.is_active:
            raise serializers.ValidationError(
                {"detail": "Your clinic is pending approval or payment. Please contact the Platform Administrator."}
            )
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.get_full_name() or user.email
        token["is_platform_admin"] = user.is_platform_admin
        return token


class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer
