from decimal import Decimal
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from billing.models import Invoice, InvoiceItem
from .models import Visit

@receiver(pre_save, sender=Visit)
def track_previous_status(sender, instance, **kwargs):
    if instance.pk:
        old = Visit.all_objects.get(pk=instance.pk)
        instance._previous_status = old.status
    else:
        instance._previous_status = None

@receiver(post_save, sender=Visit)
def auto_generate_invoice(sender, instance, created, **kwargs):
    # Trigger only when transitioning TO closed
    if created or instance.status != Visit.Status.CLOSED:
        return
    
    prev = getattr(instance, "_previous_status", None)
    if prev == Visit.Status.CLOSED:
        return

    # Don't duplicate if an invoice already exists
    if Invoice.all_objects.filter(visit=instance).exists():
        return

    with db_tenant_context(instance.tenant):
        inv = Invoice.objects.create(
            visit=instance,
            patient=instance.patient,
            status=Invoice.Status.DRAFT,
            currency="ZMW",
        )
        
        # Add consultation fee (base assumption)
        InvoiceItem.objects.create(
            invoice=inv, category=InvoiceItem.Category.CONSULTATION,
            description="OPD Consultation", quantity=1, unit_price=Decimal("150.00")
        )

        # Pull from Orders
        for order in instance.orders.all():
            for item in order.items.all():
                if order.kind == "lab":
                    from lab.models import LabTest
                    test = LabTest.objects.filter(code=item.code).first()
                    price = test.base_price if test else Decimal("0.00")
                    InvoiceItem.objects.create(
                        invoice=inv, category=InvoiceItem.Category.LAB,
                        description=item.description, quantity=item.quantity,
                        unit_price=price, order_item_code=item.code
                    )
                elif order.kind == "radiology":
                    InvoiceItem.objects.create(
                        invoice=inv, category=InvoiceItem.Category.RADIOLOGY,
                        description=item.description, quantity=item.quantity,
                        unit_price=Decimal("120.00"), order_item_code=item.code
                    )
                elif order.kind == "pharmacy":
                    from pharmacy.models import Medicine
                    med = Medicine.objects.filter(code=item.code).first()
                    price = med.base_price if med else Decimal("0.00")
                    InvoiceItem.objects.create(
                        invoice=inv, category=InvoiceItem.Category.PHARMACY,
                        description=item.description, quantity=item.quantity,
                        unit_price=price, order_item_code=item.code
                    )
                    
        inv.recalculate()
