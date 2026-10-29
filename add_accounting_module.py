#!/usr/bin/env python3
"""
add_accounting_module.py
  - Creates a double-entry accounting engine (Chart of Accounts, Journal Entries).
  - Automatically posts Journal Entries when Invoices are issued and Payments are recorded.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")

# ─── 1. Create the accounting app ──────────────────────────────────────
if not (ROOT / "accounting").exists():
    sh(PY, "manage.py", "startapp", "accounting")

# ─── 2. Models ─────────────────────────────────────────────────────────
write("accounting/models.py", '''\
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from common.models import TenantAwareModel


class ChartOfAccount(TenantAwareModel):
    class AccountType(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        REVENUE = "revenue", "Revenue"
        EXPENSE = "expense", "Expense"

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=AccountType.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_account_code"),
        ]
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(TenantAwareModel):
    date = models.DateField()
    reference = models.CharField(max_length=64, help_text="Invoice # or Payment #")
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"JE-{self.id} ({self.reference})"

    def verify_balance(self):
        """Ensure Debits == Credits. Raises error if unbalanced."""
        debits = sum(line.debit for line in self.lines.all())
        credits = sum(line.credit for line in self.lines.all())
        if debits != credits:
            raise ValidationError(f"Journal Entry is unbalanced! Debits: {debits}, Credits: {credits}")


class JournalEntryLine(TenantAwareModel):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("A line cannot have both a debit and a credit.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account.code} - D:{self.debit} C:{self.credit}"
''')

# ─── 3. Admin ──────────────────────────────────────────────────────────
write("accounting/admin.py", '''\
from django.contrib import admin
from common.admin import TenantModelAdmin
from .models import ChartOfAccount, JournalEntry, JournalEntryLine


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0


@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(TenantModelAdmin):
    list_display = ("code", "name", "type", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("code", "name")


@admin.register(JournalEntry)
class JournalEntryAdmin(TenantModelAdmin):
    list_display = ("id", "date", "reference", "description")
    list_filter = ("date",)
    search_fields = ("reference", "description")
    inlines = [JournalEntryLineInline]
''')

# ─── 4. Auto-Posting Signals ───────────────────────────────────────────
write("accounting/signals.py", '''\
import logging
from datetime import date
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from billing.models import Invoice, Payment, InvoiceItem
from common.context import get_current_tenant
from .models import ChartOfAccount, JournalEntry, JournalEntryLine

logger = logging.getLogger(__name__)


def _get_account(tenant, code):
    return ChartOfAccount.objects.filter(tenant=tenant, code=code).first()


@receiver(post_save, sender=Invoice)
def post_invoice_to_ledger(sender, instance, created, **kwargs):
    """When an invoice is issued, record AR (Debit) and Revenue (Credit)."""
    if not created and instance.status != Invoice.Status.ISSUED:
        return
    
    # Check if a JE already exists for this invoice to prevent double-posting
    if JournalEntry.all_objects.filter(tenant=instance.tenant, reference=instance.invoice_no).exists():
        return

    tenant = instance.tenant
    with transaction.atomic():
        try:
            je = JournalEntry.objects.create(
                tenant=tenant,
                date=date.today(),
                reference=instance.invoice_no,
                description=f"Invoice issued to {instance.patient.full_name}",
            )

            # Debit: Accounts Receivable (1100)
            ar_account = _get_account(tenant, "1100")
            if ar_account:
                JournalEntryLine.objects.create(
                    tenant=tenant, journal_entry=je, account=ar_account,
                    debit=instance.total, credit=Decimal("0.00")
                )

            # Credit: Revenue accounts based on items
            for item in instance.items.all():
                revenue_code = "4000" # Default Consultation
                if item.category == InvoiceItem.Category.PHARMACY:
                    revenue_code = "4100"
                elif item.category == InvoiceItem.Category.LAB:
                    revenue_code = "4200"
                elif item.category == InvoiceItem.Category.RADIOLOGY:
                    revenue_code = "4300"

                rev_account = _get_account(tenant, revenue_code)
                if rev_account:
                    JournalEntryLine.objects.create(
                        tenant=tenant, journal_entry=je, account=rev_account,
                        debit=Decimal("0.00"), credit=item.total
                    )

            je.verify_balance()
        except Exception as e:
            logger.error(f"Failed to post invoice {instance.invoice_no} to ledger: {e}")


@receiver(post_save, sender=Payment)
def post_payment_to_ledger(sender, instance, created, **kwargs):
    """When a payment is received, record Cash (Debit) and AR (Credit)."""
    if not created:
        return

    tenant = instance.tenant
    with transaction.atomic():
        try:
            je = JournalEntry.objects.create(
                tenant=tenant,
                date=date.today(),
                reference=f"PAY-{instance.id}",
                description=f"Payment received via {instance.method}",
            )

            # Debit: Cash/MoMo (1000)
            cash_account = _get_account(tenant, "1000")
            if cash_account:
                JournalEntryLine.objects.create(
                    tenant=tenant, journal_entry=je, account=cash_account,
                    debit=instance.amount, credit=Decimal("0.00")
                )

            # Credit: Accounts Receivable (1100)
            ar_account = _get_account(tenant, "1100")
            if ar_account:
                JournalEntryLine.objects.create(
                    tenant=tenant, journal_entry=je, account=ar_account,
                    debit=Decimal("0.00"), credit=instance.amount
                )

            je.verify_balance()
        except Exception as e:
            logger.error(f"Failed to post payment {instance.id} to ledger: {e}")
''')

write("accounting/apps.py", '''\
from django.apps import AppConfig

class AccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounting"

    def ready(self):
        import accounting.signals  # noqa: F401
''')

# ─── 5. Seed COA & Update Settings ─────────────────────────────────────
print("==> Updating config/settings.py")
sp = ROOT / "config" / "settings.py"
s = sp.read_text(encoding="utf-8")
if '"accounting.apps.AccountingConfig"' not in s:
    s = s.replace('"billing",', '"billing",\n    "accounting.apps.AccountingConfig",')
    sp.write_text(s, encoding="utf-8")

print("==> Patching seed_demo.py to create Chart of Accounts")
seed = ROOT / "tenants" / "management" / "commands" / "seed_demo.py"
sc = seed.read_text(encoding="utf-8")
if "ChartOfAccount" not in sc:
    sc = sc.replace(
        "from patients.models import Patient",
        "from patients.models import Patient\nfrom accounting.models import ChartOfAccount"
    )
    coa_seed = '''
        # Seed Default Chart of Accounts
        accounts = [
            ("1000", "Cash & Bank", "asset"),
            ("1100", "Accounts Receivable", "asset"),
            ("4000", "Consultation Revenue", "revenue"),
            ("4100", "Pharmacy Revenue", "revenue"),
            ("4200", "Lab Revenue", "revenue"),
            ("4300", "Radiology Revenue", "revenue"),
        ]
        for code, name, type in accounts:
            ChartOfAccount.objects.get_or_create(
                tenant=tenant, code=code, defaults={"name": name, "type": type}
            )
'''
    sc = sc.replace("            users = self._demo_users(tenant)", coa_seed + "\n            users = self._demo_users(tenant)")
    seed.write_text(sc, encoding="utf-8")

# ─── 6. Migrate & Run ──────────────────────────────────────────────────
print("==> makemigrations accounting")
sh(PY, "manage.py", "makemigrations", "accounting")

print("==> migrate")
sh(PY, "manage.py", "migrate")

print("==> Done! Push to GitHub and redeploy both services.")