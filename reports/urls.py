from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_index, name="reports_index"),
    path("production/", views.production_report, name="production_report"),
    path("mortality/", views.mortality_report, name="mortality_report"),
    path("sales/", views.sales_report, name="sales_report"),
    path("expenses/", views.expense_report, name="expense_report"),
    path("inventory/", views.inventory_report, name="inventory_report"),
    path("profit-loss/", views.profit_loss_report, name="profit_loss_report"),
    path("production/export-excel/", views.export_production_excel, name="export_production_excel"),
    path("mortality/export-excel/", views.export_mortality_excel, name="export_mortality_excel"),
    path("sales/export-excel/", views.export_sales_excel, name="export_sales_excel"),
    path("expenses/export-excel/", views.export_expense_excel, name="export_expense_excel"),
    path("inventory/export-excel/", views.export_inventory_excel, name="export_inventory_excel"),
    path("profit-loss/export-excel/", views.export_profit_loss_excel, name="export_profit_loss_excel"),
]
