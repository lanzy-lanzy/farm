from django.urls import path

from . import views

app_name = "feeding"

urlpatterns = [
    path("", views.feeding_list, name="feeding_list"),
    path("create/", views.feeding_create, name="feeding_create"),
    path("<int:pk>/edit/", views.feeding_update, name="feeding_update"),
    path("<int:pk>/delete/", views.feeding_delete, name="feeding_delete"),
    path("history/<int:flock_id>/", views.feeding_history, name="feeding_history"),
]
