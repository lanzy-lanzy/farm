from django.urls import path

from . import views

app_name = "suppliers"

urlpatterns = [
    path("", views.supplier_list, name="supplier_list"),
    path("create/", views.supplier_create, name="supplier_create"),
    path("<int:pk>/edit/", views.supplier_update, name="supplier_update"),
    path("<int:pk>/delete/", views.supplier_delete, name="supplier_delete"),
    path("<int:pk>/account/create/", views.supplier_create_account, name="supplier_create_account"),
    path("<int:pk>/account/deactivate/", views.supplier_deactivate_account, name="supplier_deactivate_account"),
]
