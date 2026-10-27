from django.db import models
from common.models import TenantAwareModel


class SmsLog(TenantAwareModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT   = "sent", "Sent"
        FAILED = "failed", "Failed"

    recipient = models.CharField(max_length=32)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=32, blank=True)
    provider_message_id = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SMS to {self.recipient} ({self.status})"
