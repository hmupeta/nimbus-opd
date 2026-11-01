from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder

def _check_and_complete_parent_order(sub_order):
    """If all sub-orders for a parent are completed, mark the parent as completed."""
    parent = sub_order.order
    if not parent:
        return
    
    if parent.status == Order.Status.COMPLETED:
        return
        
    all_done = True
    if parent.kind == Order.Kind.LAB:
        subs = LabOrder.all_objects.filter(order=parent)
        all_done = all(s.status in ["completed", "cancelled"] for s in subs)
    elif parent.kind == Order.Kind.RADIOLOGY:
        subs = RadiologyOrder.all_objects.filter(order=parent)
        all_done = all(s.status in ["reported", "cancelled"] for s in subs)
    elif parent.kind == Order.Kind.PHARMACY:
        subs = PharmacyOrder.all_objects.filter(order=parent)
        all_done = all(s.status in ["dispensed", "cancelled"] for s in subs)
        
    if all_done:
        parent.status = Order.Status.COMPLETED
        parent.save(update_fields=["status"])

@receiver(post_save, sender=LabOrder)
def sync_lab_order(sender, instance, **kwargs):
    _check_and_complete_parent_order(instance)

@receiver(post_save, sender=RadiologyOrder)
def sync_rad_order(sender, instance, **kwargs):
    _check_and_complete_parent_order(instance)

@receiver(post_save, sender=PharmacyOrder)
def sync_pharm_order(sender, instance, **kwargs):
    _check_and_complete_parent_order(instance)