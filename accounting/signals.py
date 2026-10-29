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
                status=JournalEntry.Status.PENDING,
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
                status=JournalEntry.Status.PENDING,
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
