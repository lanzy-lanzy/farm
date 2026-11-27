from django.urls import path

from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.settings_view, name="settings"),
    path("farm/", views.farm_settings, name="farm_settings"),
    path("order-workflow/", views.order_workflow_settings, name="order_workflow_settings"),
    path("lan-sharing/", views.lan_sharing, name="lan_sharing"),
]
