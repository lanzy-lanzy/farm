from django.urls import path

from . import views

app_name = "flocks"

urlpatterns = [
    path("", views.flock_list, name="flock_list"),
    path("create/", views.flock_create, name="flock_create"),
    path("<int:pk>/", views.flock_detail, name="flock_detail"),
    path("<int:pk>/edit/", views.flock_update, name="flock_update"),
    path("<int:pk>/delete/", views.flock_delete, name="flock_delete"),
]
