from django.db import models

from common.context import get_current_tenant
from common.models import TenantAwareModel
from patients.models import Patient, next_sequence


class Visit(TenantAwareModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        TRIAGED = "triaged", "Triaged"
        IN_CONSULTATION = "in_consultation", "In consultation"
        AWAITING_RESULTS = "awaiting_results", "Awaiting results"
        PHARMACY = "pharmacy", "Pharmacy"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    class Type(models.TextChoices):
        OPD = "OPD", "Outpatient"
        ER = "ER", "Emergency"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="visits")
    visit_no = models.CharField(max_length=32, blank=True, db_index=True)
    visit_type = models.CharField(max_length=8, choices=Type.choices, default=Type.OPD)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    arrived_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    attending_doctor = models.ForeignKey(
        "tenants.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "visit_no"], name="uniq_visit_no"),
        ]
        indexes = [models.Index(fields=["tenant", "patient", "arrived_at"])]
    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            tenant = get_current_tenant()
            if tenant is not None:
                self.tenant = tenant
        if not self.visit_no:
            if self.tenant_id is None:
                raise ValueError("Tenant required to generate visit_no")
            self.visit_no = f"V{next_sequence(self.tenant, 'visit'):08d}"
        super().save(*args, **kwargs)
