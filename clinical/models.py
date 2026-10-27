from django.db import models

from common.models import TenantAwareModel


class ClinicalNote(TenantAwareModel):
    class Kind(models.TextChoices):
        SOAP = "soap", "SOAP"
        PROGRESS = "progress", "Progress"
        CONSULT = "consult", "Consult"

    visit = models.ForeignKey("visits.Visit", on_delete=models.CASCADE, related_name="notes")
    doctor = models.ForeignKey("tenants.User", on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SOAP)
    subjective = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Order(TenantAwareModel):
    class Kind(models.TextChoices):
        LAB = "lab", "Lab"
        RADIOLOGY = "radiology", "Radiology"
        PHARMACY = "pharmacy", "Pharmacy"
        PROCEDURE = "procedure", "Procedure"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        STAT = "stat", "STAT"

    visit = models.ForeignKey("visits.Visit", on_delete=models.CASCADE, related_name="orders")
    ordered_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    priority = models.CharField(max_length=8, choices=Priority.choices,
                                default=Priority.ROUTINE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "visit", "kind", "status"])]


class OrderItem(TenantAwareModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    code = models.CharField(max_length=64)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    instructions = models.TextField(blank=True)
