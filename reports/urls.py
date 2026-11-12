from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_index, name="reports_index"),
    path("production/", views.production_report, name="production_report"),
    path("deaths/", views.death_report, name="death_report"),
    path("sales/", views.sales_report, name="sales_report"),
    path("expenses/", views.expense_report, name="expense_report"),
    path("inventory/", views.inventory_report, name="inventory_report"),
    path("profit-loss/", views.profit_loss_report, name="profit_loss_report"),
    path("production/print/", views.production_report_print, name="production_report_print"),
    path("deaths/print/", views.death_report_print, name="death_report_print"),
    path("sales/print/", views.sales_report_print, name="sales_report_print"),
    path("expenses/print/", views.expense_report_print, name="expense_report_print"),
    path("inventory/print/", views.inventory_report_print, name="inventory_report_print"),
    path("profit-loss/print/", views.profit_loss_report_print, name="profit_loss_report_print"),
    path("production/export-excel/", views.export_production_excel, name="export_production_excel"),
    path("deaths/export-excel/", views.export_death_excel, name="export_death_excel"),
    path("sales/export-excel/", views.export_sales_excel, name="export_sales_excel"),
    path("expenses/export-excel/", views.export_expense_excel, name="export_expense_excel"),
    path("inventory/export-excel/", views.export_inventory_excel, name="export_inventory_excel"),
    path("profit-loss/export-excel/", views.export_profit_loss_excel, name="export_profit_loss_excel"),
    path("production/export-pdf/", views.export_production_pdf, name="export_production_pdf"),
    path("deaths/export-pdf/", views.export_death_pdf, name="export_death_pdf"),
    path("sales/export-pdf/", views.export_sales_pdf, name="export_sales_pdf"),
    path("expenses/export-pdf/", views.export_expense_pdf, name="export_expense_pdf"),
    path("inventory/export-pdf/", views.export_inventory_pdf, name="export_inventory_pdf"),
    path("profit-loss/export-pdf/", views.export_profit_loss_pdf, name="export_profit_loss_pdf"),
]
