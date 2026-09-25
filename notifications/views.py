from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.access import internal_only
from config.htmx import is_htmx, modal_closed

from .forms import NotificationComposeForm, NotificationForm
from .models import Notification, ActivityLog
from .utils import log_activity, notify_team, notify_user


def _mine(request, pk):
    """The signed-in user's own copy of a notification, or a 404.

    Every notification is a per-user row, so inbox actions (read, edit, dismiss)
    only ever touch the copy belonging to the person asking. Each view below is
    already guarded by internal_only or login_required.
    """
    return get_object_or_404(Notification, pk=pk, user=request.user)


def _processing_url(request, notification):
    """Where a click on a notification should land: the page that handles the event.

    Links are validated rather than trusted, so a stored address can never send a
    user off-site; anything unsafe falls back to the notification list.
    """
    link = notification.link or ""
    if url_has_allowed_host_and_scheme(
        link, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return link
    return None


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    unread_only = request.GET.get("filter") == "unread"
    if unread_only:
        notifications = notifications.filter(is_read=False)
    template = (
        "portal/notifications.html"
        if request.user.is_external()
        else "notifications/notification_list.html"
    )
    return render(
        request,
        template,
        {"notifications": notifications, "unread_only": unread_only},
    )


@login_required
def notification_mark_read(request, pk):
    """Flag the notification as seen, then continue to the page that acts on it.

    Only a real browser navigation follows the link: the title, the Process shortcut,
    the bell row and the portal row are plain anchors, so they mark it read and land on
    notification.link. An HTMX request comes from the "Mark read" button inside the
    detail dialog, whose job is to close the dialog and refresh the inbox - never to
    move the browser - so it must not redirect, even when the notice carries a link.
    """
    notification = _mine(request, pk)
    if not notification.is_read:
        notification.mark_as_read()
    if is_htmx(request):
        return modal_closed()
    destination = _processing_url(request, notification)
    if destination:
        return redirect(destination)
    return redirect("notifications:notification_list")


@internal_only
def notification_mark_unread(request, pk):
    notification = _mine(request, pk)
    if request.method == "POST":
        notification.is_read = False
        notification.save()
        if is_htmx(request):
            return modal_closed()
        return redirect("notifications:notification_list")
    return redirect("notifications:notification_list")


@internal_only
def notification_mark_all_read(request):
    if request.method == "POST":
        updated = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        messages.success(
            request,
            "All notifications marked as read." if updated else "Nothing was unread.",
        )
        if is_htmx(request):
            return modal_closed()
    return redirect("notifications:notification_list")


@internal_only
def notification_detail(request, pk):
    """Read side of the inbox CRUD — a modal fragment over the unified list page."""
    notification = _mine(request, pk)
    if not is_htmx(request):
        return redirect("notifications:notification_list")
    return render(request, "notifications/_detail.html", {"notification": notification})


@internal_only
def notification_create(request):
    if request.method == "POST":
        form = NotificationComposeForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            link = data.get("link") or None
            if data["audience"] == "team":
                notify_team(
                    data["notification_type"], data["title"], data["message"], link=link
                )
                log_activity(
                    request.user, "create", "Notification", None, data["title"],
                    "Posted a team notification",
                )
                messages.success(request, f"'{data['title']}' sent to the farm team.")
            else:
                notify_user(
                    request.user,
                    data["notification_type"], data["title"], data["message"], link=link
                )
                messages.success(request, f"'{data['title']}' added to your notifications.")
            if is_htmx(request):
                return modal_closed()
            return redirect("notifications:notification_list")
    elif not is_htmx(request):
        return redirect("notifications:notification_list")
    else:
        form = NotificationComposeForm()
    return render(request, "notifications/_form.html", {"form": form})


@internal_only
def notification_update(request, pk):
    notification = _mine(request, pk)
    if request.method == "POST":
        form = NotificationForm(request.POST, instance=notification)
        if form.is_valid():
            form.save()
            log_activity(
                request.user, "update", "Notification", notification.pk,
                notification.title, "Updated a notification",
            )
            messages.success(request, "Notification updated.")
            if is_htmx(request):
                return modal_closed()
            return redirect("notifications:notification_list")
    elif not is_htmx(request):
        return redirect("notifications:notification_list")
    else:
        form = NotificationForm(instance=notification)
    return render(
        request,
        "notifications/_form.html",
        {"form": form, "notification": notification},
    )


@internal_only
def notification_delete(request, pk):
    notification = _mine(request, pk)
    if request.method == "POST":
        title = notification.title
        log_activity(
            request.user, "delete", "Notification", notification.pk, title,
            "Dismissed a notification",
        )
        notification.delete()
        messages.success(request, f"'{title}' dismissed.")
        if is_htmx(request):
            return modal_closed()
        return redirect("notifications:notification_list")
    if not is_htmx(request):
        return redirect("notifications:notification_list")
    return render(request, "notifications/_delete.html", {"notification": notification})


@internal_only
def activity_log(request):
    activities = ActivityLog.objects.all()[:100]
    return render(request, "notifications/activity_log.html", {"activities": activities})
