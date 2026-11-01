from django.db import models
from common.models import TenantAwareModel

class MomoTransaction(TenantAwareModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESSFUL = "SUCCESSFUL", "Successful"
        FAILED = "FAILED", "Failed"

    invoice = models.ForeignKey("billing.Invoice", on_delete=models.CASCADE, related_name="momo_transactions")
    reference_id = models.CharField(max_length=64, unique=True, help_text="MTN X-Reference-Id")
    phone_number = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    external_id = models.CharField(max_length=64, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MoMo {self.reference_id} - {self.status}"