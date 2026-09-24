from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.access import internal_only

from .models import Notification, ActivityLog


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    template = (
        "portal/notifications.html"
        if request.user.is_external()
        else "notifications/notification_list.html"
    )
    return render(request, template, {"notifications": notifications})


@login_required
def notification_mark_read(request, pk):
    notification = Notification.objects.get(pk=pk, user=request.user)
    notification.mark_as_read()
    if notification.link:
        return redirect(notification.link)
    return redirect("notifications:notification_list")


@internal_only
def activity_log(request):
    activities = ActivityLog.objects.all()[:100]
    return render(request, "notifications/activity_log.html", {"activities": activities})
