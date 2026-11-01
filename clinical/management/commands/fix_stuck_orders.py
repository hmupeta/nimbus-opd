from django.core.management.base import BaseCommand
from tenants.models import Tenant
from clinical.models import Order
from lab.models import LabOrder
from radiology.models import RadiologyOrder
from pharmacy.models import PharmacyOrder
from common.context import db_tenant_context


class Command(BaseCommand):
    help = "Auto-complete any parent Order whose sub-orders are already done."

    def handle(self, *args, **opts):
        total_fixed = 0

        for tenant in Tenant.objects.all():
            # Use the proper context manager so RLS lets us see the orders
            with db_tenant_context(tenant):
                pending = Order.all_objects.filter(
                    tenant=tenant,
                    status__in=[Order.Status.PENDING, Order.Status.IN_PROGRESS],
                )

                for order in pending:
                    should_complete = False

                    if order.kind == Order.Kind.LAB:
                        subs = LabOrder.all_objects.filter(order=order)
                        if subs.exists() and all(s.status in ["completed", "cancelled"] for s in subs):
                            should_complete = True

                    elif order.kind == Order.Kind.RADIOLOGY:
                        subs = RadiologyOrder.all_objects.filter(order=order)
                        if subs.exists() and all(s.status in ["reported", "cancelled"] for s in subs):
                            should_complete = True

                    elif order.kind == Order.Kind.PHARMACY:
                        subs = PharmacyOrder.all_objects.filter(order=order)
                        if subs.exists() and all(s.status in ["dispensed", "cancelled"] for s in subs):
                            should_complete = True

                    if should_complete:
                        order.status = Order.Status.COMPLETED
                        order.save(update_fields=["status"])
                        total_fixed += 1
                        self.stdout.write(
                            f"  [FIXED] {tenant.code}: Order #{order.id} ({order.kind})"
                        )

        self.stdout.write(self.style.SUCCESS(
            f"fix_stuck_orders: {total_fixed} order(s) completed."))