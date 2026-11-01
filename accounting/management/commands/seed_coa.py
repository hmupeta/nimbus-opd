from django.core.management.base import BaseCommand
from tenants.models import Tenant
from accounting.models import ChartOfAccount
from common.context import db_tenant_context

STANDARD_ACCOUNTS = [
    ("1000", "Cash & Bank", "asset"),
    ("1100", "Accounts Receivable", "asset"),
    ("1200", "Inventory", "asset"),
    ("1500", "Fixed Assets", "asset"),
    ("2000", "Accounts Payable", "liability"),
    ("3000", "Owner's Equity", "equity"),
    ("4000", "Consultation Revenue", "revenue"),
    ("4100", "Pharmacy Revenue", "revenue"),
    ("4200", "Lab Revenue", "revenue"),
    ("4300", "Radiology Revenue", "revenue"),
    ("5000", "Salaries & Wages", "expense"),
    ("5100", "Rent Expense", "expense"),
    ("5200", "Utilities Expense", "expense"),
    ("5300", "Medical Supplies", "expense"),
]

class Command(BaseCommand):
    help = "Seed Standard Chart of Accounts for all tenants."

    def handle(self, *args, **opts):
        total_created = 0
        
        for tenant in Tenant.objects.all():
            with db_tenant_context(tenant):
                created_count = 0
                for code, name, type in STANDARD_ACCOUNTS:
                    obj, created = ChartOfAccount.all_objects.get_or_create(
                        tenant=tenant, code=code,
                        defaults={"name": name, "type": type}
                    )
                    if created:
                        created_count += 1
                
                if created_count > 0:
                    self.stdout.write(f"[COA] {tenant.name}: created {created_count} accounts.")
                    total_created += created_count
                else:
                    self.stdout.write(f"[COA] {tenant.name}: already seeded.")
                    
        self.stdout.write(self.style.SUCCESS(f"seed_coa: {total_created} accounts created."))