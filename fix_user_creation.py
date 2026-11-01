import os
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parent
views_path = BACKEND_PATH / "core" / "views.py"

# We will append a bulletproof user creation view to core/views.py
NEW_VIEW = '''

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from core.models import BranchAccess, Company, Tenant

User = get_user_model()

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def users_list_create(request):
    """List users or create a new user."""
    if request.method == "GET":
        # Return users belonging to the same tenant
        if not request.tenant:
            return Response([])
        users = User.objects.filter(tenant=request.tenant).order_by("-date_joined")
        return Response([{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "user_type": u.user_type,
            "is_active": u.is_active,
        } for u in users])

    # --- POST: Create User ---
    data = request.data
    username = data.get("username")
    password = data.get("password")
    email = data.get("email", "")
    role = data.get("user_type", "CASHIER") # or CASHIER/DOCTOR etc based on your UI
    branch_id = data.get("branch_id")

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "A user with this username already exists."}, status=400)

    try:
        with transaction.atomic():
            # Create the user attached to the same tenant as the admin creating them
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                tenant=request.tenant,
                user_type=role,
                employment_status="ACTIVE",
                is_active=True
            )

            # Assign branch if provided
            if branch_id:
                try:
                    branch = Company.objects.get(pk=branch_id, tenant=request.tenant)
                    BranchAccess.objects.create(user=user, company=branch, is_default=True)
                except Company.DoesNotExist:
                    pass
            
            return Response({"success": True, "id": user.id}, status=201)
            
    except Exception as e:
        return Response({"error": str(e)}, status=500)
'''

# Append to views.py
with open(views_path, "a", encoding="utf-8") as f:
    f.write("\n" + NEW_VIEW)

# Update urls.py to point /api/users/ to this new view
urls_path = BACKEND_PATH / "core" / "urls.py"
with open(urls_path, "r", encoding="utf-8") as f:
    urls_content = f.read()

if "users_list_create" not in urls_content:
    urls_content = urls_content.replace(
        "urlpatterns = [",
        "from .views import users_list_create\n\nurlpatterns = [\n    path('users/', users_list_create, name='users_list_create'),"
    )
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write(urls_content)

print("✅ User creation endpoint fixed and mounted at /api/users/")