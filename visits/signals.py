from decimal import Decimal
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from common.context import db_tenant_context
from billing.models import Invoice, InvoiceItem
from clinical.models import Order
from .models import Visit

@receiver(pre_save, sender=Visit)
def track_previous_status(sender, instance, **kwargs):
    """Store the old status so we can detect the transition to 'closed'."""
    if instance.pk:
        old = Visit.all_objects.get(pk=instance.pk)
        instance._previous_status = old.status
    else:
        instance._previous_status = None

@receiver(post_save, sender=Visit)
def auto_generate_invoice(sender, instance, created, **kwargs):
    """Generate a complete invoice when a visit transitions to 'closed'."""
    if created or instance.status != Visit.Status.CLOSED:
        return
    
    prev = getattr(instance, "_previous_status", None)
    if prev == Visit.Status.CLOSED:
        return

    # If an invoice already exists (e.g., created manually), don't duplicate it
    if Invoice.all_objects.filter(visit=instance).exists():
        return

    with db_tenant_context(instance.tenant):
        inv = Invoice.objects.create(
            visit=instance,
            patient=instance.patient,
            status=Invoice.Status.DRAFT,
            currency="ZMW",
        )
        
        # 1. Consultation Fee
        InvoiceItem.objects.create(
            invoice=inv,
            category=InvoiceItem.Category.CONSULTATION,
            description="OPD Consultation",
            quantity=1,
            unit_price=Decimal("150.00")
        )

        # 2. Pull from Orders (Lab, Radiology, Pharmacy)
        for order in instance.orders.all():
            for item in order.items.all():
                price = Decimal("0.00")
                
                if order.kind == Order.Kind.LAB:
                    from lab.models import LabTest
                    test = LabTest.all_objects.filter(tenant=instance.tenant, code=item.code).first()
                    if test:
                        price = test.base_price
                
                elif order.kind == Order.Kind.RADIOLOGY:
                    from radiology.models import RadiologyExam
                    exam = RadiologyExam.all_objects.filter(tenant=instance.tenant, code=item.code).first()
                    if exam:
                        price = exam.base_price
                
                elif order.kind == Order.Kind.PHARMACY:
                    from pharmacy.models import Medicine
                    med = Medicine.all_objects.filter(tenant=instance.tenant, code=item.code).first()
                    if med:
                        price = med.base_price

                # Add to invoice
                InvoiceItem.objects.create(
                    invoice=inv,
                    category=order.kind,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=price,
                    order_item_code=item.code
                )
                
        inv.recalculate()