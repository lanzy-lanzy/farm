from django.urls import path

from . import views

app_name = "mortality"

urlpatterns = [
    path("", views.mortality_list, name="mortality_list"),
    path("create/", views.mortality_create, name="mortality_create"),
    path("<int:pk>/edit/", views.mortality_update, name="mortality_update"),
    path("<int:pk>/delete/", views.mortality_delete, name="mortality_delete"),
]
