from django.db import models

from common.models import TenantAwareModel


class LabTest(TenantAwareModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    specimen_type = models.CharField(max_length=64, blank=True)
    unit = models.CharField(max_length=24, blank=True)
    ref_low = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    ref_high = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_labtest_code"),
        ]
class LabOrder(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COLLECTED = "collected", "Collected"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    visit = models.ForeignKey("visits.Visit", on_delete=models.CASCADE,
                              related_name="lab_orders")
    order = models.ForeignKey("clinical.Order", on_delete=models.CASCADE,
                              related_name="lab_orders")
    test = models.ForeignKey(LabTest, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    ordered_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="+")


class LabResult(TenantAwareModel):
    class Flag(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        LOW = "low", "Low"
        CRITICAL = "critical", "Critical"

    lab_order = models.OneToOneField(LabOrder, on_delete=models.CASCADE, related_name="result")
    value_text = models.CharField(max_length=128)
    unit = models.CharField(max_length=24, blank=True)
    flag = models.CharField(max_length=8, choices=Flag.choices, default=Flag.NORMAL)
    comment = models.TextField(blank=True)
    resulted_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT)
    resulted_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
