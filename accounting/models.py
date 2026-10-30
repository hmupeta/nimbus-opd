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
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="uniq_account_code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    date = models.DateField()
    reference = models.CharField(max_length=64, help_text="Invoice #, Bill #, or manual ref")
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"JE-{self.id} ({self.reference})"

    def verify_balance(self):
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


class Supplier(TenantAwareModel):
    name = models.CharField(max_length=128)
    contact_name = models.CharField(max_length=128, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Bill(TenantAwareModel):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Paid"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="bills")
    reference = models.CharField(max_length=64, blank=True, help_text="Supplier invoice #")
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNPAID)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill {self.id} - {self.supplier.name} (ZMW {self.amount})"


class Expense(TenantAwareModel):
    date = models.DateField()
    category = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT, limit_choices_to={"type": "expense"})
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=32, blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Expense {self.id} - {self.description} (ZMW {self.amount})"


class FixedAsset(TenantAwareModel):
    name = models.CharField(max_length=128)
    category = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT, limit_choices_to={"type": "asset"})
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    useful_life_years = models.PositiveIntegerField(default=5)
    is_disposed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (ZMW {self.purchase_cost})"
