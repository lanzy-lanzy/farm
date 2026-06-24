from django.urls import path

from . import views

app_name = "buyers"

urlpatterns = [
    path("", views.buyer_list, name="buyer_list"),
    path("create/", views.buyer_create, name="buyer_create"),
    path("<int:pk>/edit/", views.buyer_update, name="buyer_update"),
    path("<int:pk>/delete/", views.buyer_delete, name="buyer_delete"),
]
