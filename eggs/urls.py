from django.urls import path

from . import views

app_name = "eggs"

urlpatterns = [
    path("", views.egg_list, name="egg_list"),
    path("create/", views.egg_create, name="egg_create"),
    path("<int:pk>/edit/", views.egg_update, name="egg_update"),
    path("<int:pk>/delete/", views.egg_delete, name="egg_delete"),
]
