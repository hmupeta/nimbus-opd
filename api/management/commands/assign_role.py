from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from api.roles import ROLE_CHOICES


class Command(BaseCommand):
    help = "Assign a role to a user. Usage: assign_role <username> <role>"

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=ROLE_CHOICES)

    def handle(self, username, role, *args, **opts):
        U = get_user_model()
        try:
            user = U.objects.get(username=username)
        except U.DoesNotExist:
            raise CommandError(f"No user named {username!r}")
        g = Group.objects.get(name=role)
        user.groups.add(g)
        self.stdout.write(self.style.SUCCESS(f"{username} → {role}"))
