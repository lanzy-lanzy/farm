from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.inventory_list, name="inventory_list"),
    # Standalone print / Save-as-PDF preview of the current filtered list.
    path("print/", views.inventory_print, name="inventory_print"),
    path("create/", views.inventory_create, name="inventory_create"),
    path("<int:pk>/", views.inventory_detail, name="inventory_detail"),
    path("<int:pk>/edit/", views.inventory_update, name="inventory_update"),
    path("<int:pk>/delete/", views.inventory_delete, name="inventory_delete"),
    path("transaction/create/", views.transaction_create, name="transaction_create"),
    path("transaction/create/<int:item_id>/", views.transaction_create, name="transaction_create_item"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path("units/", views.unit_list, name="unit_list"),
    path("units/create/", views.unit_create, name="unit_create"),
]
