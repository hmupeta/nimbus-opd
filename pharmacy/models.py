from django.db import models

from common.models import TenantAwareModel


class Medicine(TenantAwareModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    form = models.CharField(max_length=32, blank=True)
    strength = models.CharField(max_length=32, blank=True)
    unit = models.CharField(max_length=16, default="each")
    is_active = models.BooleanField(default=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_med_code"),
        ]
class PharmacyOrder(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DISPENSED = "dispensed", "Dispensed"
        CANCELLED = "cancelled", "Cancelled"

    visit = models.ForeignKey("visits.Visit", on_delete=models.CASCADE,
                              related_name="pharm_orders")
    order = models.ForeignKey("clinical.Order", on_delete=models.CASCADE,
                              related_name="pharm_orders")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    dispensed_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="+")
    dispensed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)


class PharmacyItem(TenantAwareModel):
    pharmacy_order = models.ForeignKey(PharmacyOrder, on_delete=models.CASCADE,
                                       related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    dose = models.CharField(max_length=64)
    frequency = models.CharField(max_length=64)
    duration_days = models.PositiveIntegerField(default=1)
    route = models.CharField(max_length=32, blank=True)
    quantity_prescribed = models.PositiveIntegerField(default=1)
    quantity_dispensed = models.PositiveIntegerField(default=0)
    batch_no = models.CharField(max_length=64, blank=True)
    expiry_date = models.DateField(null=True, blank=True)


class Stock(TenantAwareModel):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    batch_no = models.CharField(max_length=64)
    expiry_date = models.DateField()
    quantity = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "medicine", "batch_no"],
                                    name="uniq_stock_batch"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0),
                                   name="stock_non_negative"),
        ]


class StockMovement(TenantAwareModel):
    REASONS = [("dispense", "Dispense"), ("restock", "Restock"),
               ("adjust", "Adjust"), ("expire", "Expire")]

    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    batch_no = models.CharField(max_length=64, blank=True)
    change_qty = models.IntegerField()
    reason = models.CharField(max_length=32, choices=REASONS)
    ref_id = models.UUIDField(null=True, blank=True)
    created_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
