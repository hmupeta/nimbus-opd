from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from tenants.models import Tenant
from common.context import db_tenant_context
from accounting.models import ChartOfAccount, JournalEntry, JournalEntryLine
from billing.models import Invoice, Payment, InvoiceItem


class Command(BaseCommand):
    help = "Backfill Journal Entries for historical invoices and payments."

    def _get_account(self, tenant, code):
        return ChartOfAccount.all_objects.filter(tenant=tenant, code=code).first()

    def handle(self, *args, **opts):
        invoices_fixed = 0
        payments_fixed = 0

        try:
            for tenant in Tenant.objects.all():
                with db_tenant_context(tenant):
                    # 1. Backfill Invoices
                    invoices = Invoice.all_objects.filter(tenant=tenant)
                    for inv in invoices:
                        # Delete existing empty JEs for this invoice
                        JournalEntry.all_objects.filter(
                            tenant=tenant, reference=inv.invoice_no
                        ).delete()

                        with transaction.atomic():
                            je = JournalEntry.objects.create(
                                tenant=tenant, date=inv.created_at.date(),
                                reference=inv.invoice_no,
                                description=f"Invoice issued to {inv.patient.full_name}",
                            )
                            ar = self._get_account(tenant, "1100")
                            if ar:
                                JournalEntryLine.objects.create(
                                    tenant=tenant, journal_entry=je, account=ar,
                                    debit=inv.total, credit=Decimal("0.00")
                                )
                            for item in inv.items.all():
                                code = "4000"
                                if item.category == InvoiceItem.Category.PHARMACY: code = "4100"
                                elif item.category == InvoiceItem.Category.LAB: code = "4200"
                                elif item.category == InvoiceItem.Category.RADIOLOGY: code = "4300"

                                rev = self._get_account(tenant, code)
                                if rev:
                                    JournalEntryLine.objects.create(
                                        tenant=tenant, journal_entry=je, account=rev,
                                        debit=Decimal("0.00"), credit=item.total
                                    )
                            invoices_fixed += 1

                    # 2. Backfill Payments
                    payments = Payment.all_objects.filter(tenant=tenant)
                    for pay in payments:
                        ref = f"PAY-{pay.id}"
                        JournalEntry.all_objects.filter(tenant=tenant, reference=ref).delete()
                        
                        with transaction.atomic():
                            je = JournalEntry.objects.create(
                                tenant=tenant, date=pay.paid_at.date(),
                                reference=ref,
                                description=f"Payment received via {pay.method}",
                            )
                            cash = self._get_account(tenant, "1000")
                            if cash:
                                JournalEntryLine.objects.create(
                                    tenant=tenant, journal_entry=je, account=cash,
                                    debit=pay.amount, credit=Decimal("0.00")
                                )
                            ar = self._get_account(tenant, "1100")
                            if ar:
                                JournalEntryLine.objects.create(
                                    tenant=tenant, journal_entry=je, account=ar,
                                    debit=Decimal("0.00"), credit=pay.amount
                                )
                            payments_fixed += 1

            self.stdout.write(self.style.SUCCESS(
                f"Backfilled {invoices_fixed} invoices and {payments_fixed} payments."
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Backfill failed: {e}"))