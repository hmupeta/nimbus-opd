import decimal
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from common.context import (
    get_current_ip, get_current_tenant, get_current_user, is_audit_suspended,
)
from common.models import TenantAwareModel

from .models import AuditLog

logger = logging.getLogger(__name__)


def serialize_instance(instance):
    """Convert a model instance to a JSON-safe dict, redacting sensitive fields."""
    if instance is None:
        return None
    data = {}
    for field in instance._meta.fields:
        try:
            val = getattr(instance, field.attname)
        except Exception:
            val = None

        if field.name == "password":
            val = "<redacted>"
        elif isinstance(val, decimal.Decimal):
            val = float(val)
        elif hasattr(val, "isoformat"):
            val = val.isoformat()
        elif hasattr(val, "hex"):
            val = str(val)
        data[field.name] = val
    return data


def log_action(instance, action, before, after):
    if is_audit_suspended():
        return
    if isinstance(instance, AuditLog):
        return
    if not isinstance(instance, TenantAwareModel):
        return

    tenant = get_current_tenant() or getattr(instance, "tenant", None)
    if not tenant:
        return

    user = get_current_user()
    if user and not user.is_authenticated:
        user = None

    try:
        with transaction.atomic():
            AuditLog.all_objects.create(
                tenant=tenant,
                user=user,
                action=action,
                content_type=ContentType.objects.get_for_model(instance),
                object_id=str(instance.pk),
                before=before,
                after=after,
                ip=get_current_ip(),
            )
    except Exception as e:
        logger.error(f"Failed to write audit log for {instance}: {e}")


@receiver(pre_save)
def pre_save_handler(sender, instance, **kwargs):
    if is_audit_suspended():
        return
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    if not instance.pk:
        instance._audit_before = None
        return
    try:
        old = sender.all_objects.get(pk=instance.pk)
        instance._audit_before = serialize_instance(old)
    except sender.DoesNotExist:
        instance._audit_before = None


@receiver(post_save)
def post_save_handler(sender, instance, created, **kwargs):
    if is_audit_suspended():
        return
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    if created:
        log_action(instance, "create", None, serialize_instance(instance))
    else:
        before = getattr(instance, "_audit_before", None)
        after = serialize_instance(instance)
        if before != after:
            log_action(instance, "update", before, after)


@receiver(pre_delete)
def pre_delete_handler(sender, instance, **kwargs):
    if is_audit_suspended():
        return
    if not isinstance(instance, TenantAwareModel) or isinstance(instance, AuditLog):
        return
    log_action(instance, "delete", serialize_instance(instance), None)
