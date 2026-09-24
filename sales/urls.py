from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.sales_list, name="sales_list"),
    path("requests/", views.order_request_queue, name="order_request_queue"),
    path("requests/create-on-behalf/", views.order_request_create_internal, name="order_request_create_internal"),
    path("requests/<int:pk>/", views.order_request_review, name="order_request_review"),
    path("requests/<int:pk>/convert/", views.order_request_convert, name="order_request_convert"),
    path("create/", views.sales_create, name="sales_create"),
    path("<int:pk>/", views.sales_detail, name="sales_detail"),
    path("<int:pk>/edit/", views.sales_update, name="sales_update"),
    path("<int:pk>/delete/", views.sales_delete, name="sales_delete"),
]
