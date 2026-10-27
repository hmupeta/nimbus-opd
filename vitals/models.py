from django.core.validators import MinValueValidator
from django.db import models

from common.models import TenantAwareModel


class Vitals(TenantAwareModel):
    visit = models.OneToOneField("visits.Visit", on_delete=models.CASCADE, related_name="vitals")
    recorded_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now=True)

    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    pulse = models.PositiveSmallIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    spo2 = models.PositiveSmallIntegerField(null=True, blank=True)
    pain_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)


class VitalDefinition(TenantAwareModel):
    code = models.SlugField(max_length=48)
    label = models.CharField(max_length=96)
    unit = models.CharField(max_length=24, blank=True)
    data_type = models.CharField(max_length=8, choices=[
        ("num", "Numeric"), ("text", "Text"), ("bool", "Boolean"),
    ], default="num")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_vital_code"),
        ]


class VitalValue(TenantAwareModel):
    visit = models.ForeignKey("visits.Visit", on_delete=models.CASCADE,
                              related_name="extra_vitals")
    definition = models.ForeignKey(VitalDefinition, on_delete=models.PROTECT)
    value_num = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    value_text = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey("tenants.User", on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)
