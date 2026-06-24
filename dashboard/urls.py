from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("profile/", views.farm_profile, name="farm_profile"),
]
