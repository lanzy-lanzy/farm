from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Notification, ActivityLog

User = get_user_model()


def create_notification(user, notification_type, title, message, link=None, target=None):
    notification, created = Notification.objects.get_or_create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
        target=target,
        is_read=False,
    )
    return notification


def notify_team(notification_type, title, message, link=None, target=None):
    """Notify all internal (farm) users about an event from the buyer/supplier portal."""
    users = User.objects.filter(is_active=True, role__in=["admin", "owner", "staff"])
    for user in users:
        create_notification(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            target=target,
        )


def notify_user(user, notification_type, title, message, link=None, target=None):
    if user is not None and user.is_active:
        create_notification(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            target=target,
        )


def notify_low_stock(item, request=None):
    users = User.objects.filter(is_active=True, role__in=["admin", "owner", "staff"])
    for user in users:
        create_notification(
            user=user,
            notification_type="low_stock",
            title=f"Low Stock: {item.name}",
            message=f"{item.name} has only {item.quantity} {item.unit.abbreviation} remaining (reorder at {item.reorder_level}).",
            link="/inventory/",
        )


def notify_expired(item, request=None):
    users = User.objects.filter(is_active=True, role__in=["admin", "owner", "staff"])
    for user in users:
        create_notification(
            user=user,
            notification_type="expired",
            title=f"Expired: {item.name}",
            message=f"{item.name} expired on {item.expiration_date}.",
            link="/inventory/",
        )


def notify_vaccination_due(record, request=None):
    users = User.objects.filter(is_active=True, role__in=["admin", "owner", "staff"])
    for user in users:
        create_notification(
            user=user,
            notification_type="vaccination",
            title=f"Vaccination Due: {record.medicine_name}",
            message=f"{record.medicine_name} for {record.flock.batch_number} is due on {record.next_schedule}.",
            link="/medicine/",
        )


def log_activity(user, action, model_name, object_id=None, object_repr="", description=""):
    ActivityLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_repr=str(object_repr)[:200],
        description=description,
    )


def check_and_notify_inventory(item, request=None):
    if item.is_low_stock():
        notify_low_stock(item, request)
    if item.is_expired():
        notify_expired(item, request)


def check_and_notify_vaccinations():
    from medicine.models import MedicineRecord

    today = timezone.now().date()
    week_from_now = today + timezone.timedelta(days=7)
    upcoming = MedicineRecord.objects.filter(
        medicine_type="vaccine",
        next_schedule__gte=today,
        next_schedule__lte=week_from_now,
    )
    for record in upcoming:
        notify_vaccination_due(record)