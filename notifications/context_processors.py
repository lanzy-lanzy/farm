from .models import Notification


def notification_context(request):
    """Bell-badge count plus the short list behind the top-bar dropdown.

    The queryset stays lazy: shells that never render it (the partner portal,
    print pages) issue no extra query beyond the badge count.
    """
    if request.user.is_authenticated:
        mine = Notification.objects.filter(user=request.user)
        return {
            "unread_notifications": mine.filter(is_read=False).count(),
            "recent_notifications": mine[:6],
        }
    return {"unread_notifications": 0, "recent_notifications": ()}
