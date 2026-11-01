from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.roles import get_user_role, has_role, ACCOUNTANT, FINANCE_MANAGER


class RoleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            "role": get_user_role(u),
            "is_accountant": has_role(u, ACCOUNTANT),
            "is_finance_manager": has_role(u, FINANCE_MANAGER),
            "username": u.get_username(),
            "is_superuser": u.is_superuser,
        })
