from django.urls import path

from . import views

app_name = "medicine"

urlpatterns = [
    path("", views.medicine_list, name="medicine_list"),
    path("create/", views.medicine_create, name="medicine_create"),
    path("<int:pk>/edit/", views.medicine_update, name="medicine_update"),
    path("<int:pk>/delete/", views.medicine_delete, name="medicine_delete"),
    path("vaccination-schedule/", views.vaccination_schedule, name="vaccination_schedule"),
]
