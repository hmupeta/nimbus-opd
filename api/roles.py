"""Role constants, helpers, and DRF permission classes.

Roles are stored in Django Groups so no migration of the User model is
needed. Assign with:  python manage.py assign_role <username> "Accountant"
"""
from rest_framework.permissions import BasePermission

ACCOUNTANT = "Accountant"
FINANCE_MANAGER = "Finance Manager"
ROLE_CHOICES = (ACCOUNTANT, FINANCE_MANAGER)


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "Admin"
    names = set(user.groups.values_list("name", flat=True))
    if FINANCE_MANAGER in names:
        return FINANCE_MANAGER
    if ACCOUNTANT in names:
        return ACCOUNTANT
    if user.is_staff:
        return "Staff"
    return None


def has_role(user, role):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=role).exists()


class IsAccountant(BasePermission):
    message = "Accountant role required."
    def has_permission(self, request, view):
        return has_role(request.user, ACCOUNTANT)


class IsFinanceManager(BasePermission):
    message = "Finance Manager role required."
    def has_permission(self, request, view):
        return has_role(request.user, FINANCE_MANAGER)


class IsAccountantOrFinanceManager(BasePermission):
    message = "Accountant or Finance Manager role required."
    def has_permission(self, request, view):
        u = request.user
        return (u.is_superuser or has_role(u, ACCOUNTANT)
                or has_role(u, FINANCE_MANAGER))
