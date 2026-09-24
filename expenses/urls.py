from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("deliveries/", views.delivery_notice_queue, name="delivery_notice_queue"),
    path("deliveries/create/", views.delivery_notice_create, name="delivery_notice_create"),
    path("deliveries/<int:pk>/", views.delivery_notice_review, name="delivery_notice_review"),
    path("create/", views.expense_create, name="expense_create"),
    path("<int:pk>/edit/", views.expense_update, name="expense_update"),
    path("<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("categories/", views.expense_category_list, name="expense_category_list"),
    path("categories/create/", views.expense_category_create, name="expense_category_create"),
]
