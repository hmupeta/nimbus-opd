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
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
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
