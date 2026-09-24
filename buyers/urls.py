from django.urls import path

from . import views

app_name = "buyers"

urlpatterns = [
    path("", views.buyer_list, name="buyer_list"),
    path("create/", views.buyer_create, name="buyer_create"),
    path("<int:pk>/edit/", views.buyer_update, name="buyer_update"),
    path("<int:pk>/delete/", views.buyer_delete, name="buyer_delete"),
    path("<int:pk>/account/create/", views.buyer_create_account, name="buyer_create_account"),
    path("<int:pk>/account/deactivate/", views.buyer_deactivate_account, name="buyer_deactivate_account"),
]
