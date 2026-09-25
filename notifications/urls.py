from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    # One inbox page; every CRUD action runs in an HTMX modal on top of it.
    path("", views.notification_list, name="notification_list"),
    path("compose/", views.notification_create, name="notification_create"),
    path("mark-all-read/", views.notification_mark_all_read, name="notification_mark_all_read"),
    path("<int:pk>/", views.notification_detail, name="notification_detail"),
    # Marks the item seen, then forwards to the page where it gets handled.
    path("<int:pk>/read/", views.notification_mark_read, name="notification_mark_read"),
    path("<int:pk>/unread/", views.notification_mark_unread, name="notification_mark_unread"),
    path("<int:pk>/edit/", views.notification_update, name="notification_update"),
    path("<int:pk>/delete/", views.notification_delete, name="notification_delete"),
    path("activity-log/", views.activity_log, name="activity_log"),
]
