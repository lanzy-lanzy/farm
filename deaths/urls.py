from django.urls import path

from . import views

app_name = "deaths"

urlpatterns = [
    path("", views.death_list, name="death_list"),
    path("create/", views.death_create, name="death_create"),
    path("<int:pk>/edit/", views.death_update, name="death_update"),
    path("<int:pk>/delete/", views.death_delete, name="death_delete"),
]
