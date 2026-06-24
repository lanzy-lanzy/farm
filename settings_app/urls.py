from django.urls import path

from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.settings_view, name="settings"),
    path("farm/", views.farm_settings, name="farm_settings"),
]
