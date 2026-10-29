from django.db import models

from common.models import TenantAwareModel


class RadiologyOrder(TenantAwareModel):
    class Modality(models.TextChoices):
        XRAY = "X-ray", "X-ray"
        CT = "CT", "CT"
        MRI = "MRI", "MRI"
        US = "US", "Ultrasound"
        MAMMO = "Mammo", "Mammography"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SCHEDULED = "scheduled", "Scheduled"
        PERFORMED = "performed", "Performed"
        REPORTED = "reported", "Reported"
        CANCELLED = "cancelled", "Cancelled"

    visit = models.ForeignKey("visits.Visit", on_delete=models.CASCADE,
                              related_name="rad_orders")
    order = models.ForeignKey("clinical.Order", on_delete=models.CASCADE,
                              related_name="rad_orders")
    modality = models.CharField(max_length=8, choices=Modality.choices)
    body_part = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    ordered_at = models.DateTimeField(auto_now_add=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    performed_by = models.ForeignKey("tenants.User", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="+")
    findings = models.TextField(blank=True)
    impression = models.TextField(blank=True)
    radiologist = models.ForeignKey("tenants.User", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
    report_url = models.URLField(blank=True)
    image = models.ImageField(upload_to="radiology/", null=True, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)



class RadiologyExam(TenantAwareModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    modality = models.CharField(max_length=8, choices=RadiologyOrder.Modality.choices)
    body_part = models.CharField(max_length=64)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_radexam_code"),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
