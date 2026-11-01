from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from api.roles import ACCOUNTANT, FINANCE_MANAGER


class Command(BaseCommand):
    help = "Create the Accountant and Finance Manager groups."

    def handle(self, *args, **opts):
        for name in (ACCOUNTANT, FINANCE_MANAGER):
            g, created = Group.objects.get_or_create(name=name)
            self.stdout.write(f"{'created' if created else 'exists '}: {name}")
