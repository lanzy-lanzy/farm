import openpyxl
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from flocks.models import FlockBatch
from inventory.models import InventoryItem
from eggs.models import EggProduction
from mortality.models import MortalityRecord
from sales.models import SalesRecord
from expenses.models import ExpenseRecord


@login_required
def reports_index(request):
    return render(request, "reports/reports_index.html")


@login_required
def production_report(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)

    records = EggProduction.objects.filter(production_date__gte=month_ago)
    total_eggs = records.aggregate(total=Sum("total_eggs"))["total"] or 0
    total_good = records.aggregate(total=Sum("good_eggs"))["total"] or 0
    total_cracked = records.aggregate(total=Sum("cracked_eggs"))["total"] or 0
    total_rejected = records.aggregate(total=Sum("rejected_eggs"))["total"] or 0

    context = {
        "records": records,
        "total_eggs": total_eggs,
        "total_good": total_good,
        "total_cracked": total_cracked,
        "total_rejected": total_rejected,
    }
    return render(request, "reports/production_report.html", context)


@login_required
def mortality_report(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)

    records = MortalityRecord.objects.filter(date_recorded__gte=month_ago)
    total_mortality = records.aggregate(total=Sum("quantity"))["total"] or 0

    context = {
        "records": records,
        "total_mortality": total_mortality,
    }
    return render(request, "reports/mortality_report.html", context)


@login_required
def sales_report(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)

    records = SalesRecord.objects.filter(date_sold__gte=month_ago)
    total_sales = records.aggregate(total=Sum("total_amount"))["total"] or 0

    context = {
        "records": records,
        "total_sales": total_sales,
    }
    return render(request, "reports/sales_report.html", context)


@login_required
def expense_report(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)

    records = ExpenseRecord.objects.filter(expense_date__gte=month_ago)
    total_expenses = records.aggregate(total=Sum("amount"))["total"] or 0

    context = {
        "records": records,
        "total_expenses": total_expenses,
    }
    return render(request, "reports/expense_report.html", context)


@login_required
def inventory_report(request):
    items = InventoryItem.objects.filter(is_active=True)
    low_stock = items.filter(quantity__lte=models.F("reorder_level"))
    expired = items.filter(
        expiration_date__lte=timezone.now().date(), expiration_date__isnull=False
    )

    context = {
        "items": items,
        "low_stock": low_stock,
        "expired": expired,
    }
    return render(request, "reports/inventory_report.html", context)


@login_required
def profit_loss_report(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)

    total_sales = SalesRecord.objects.filter(
        date_sold__gte=month_ago
    ).aggregate(total=Sum("total_amount"))["total"] or 0

    total_expenses = ExpenseRecord.objects.filter(
        expense_date__gte=month_ago
    ).aggregate(total=Sum("amount"))["total"] or 0

    profit_loss = total_sales - total_expenses

    context = {
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "profit_loss": profit_loss,
    }
    return render(request, "reports/profit_loss_report.html", context)


def _export_to_excel(rows, headers, filename):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for col in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 3
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response


@login_required
def export_production_excel(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)
    records = EggProduction.objects.filter(production_date__gte=month_ago)
    rows = [[r.production_date, str(r.flock.batch_number), r.total_eggs, r.good_eggs, r.cracked_eggs, r.rejected_eggs] for r in records]
    return _export_to_excel(rows, ["Date", "Flock", "Total Eggs", "Good", "Cracked", "Rejected"], "production_report")


@login_required
def export_mortality_excel(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)
    records = MortalityRecord.objects.filter(date_recorded__gte=month_ago)
    rows = [[r.date_recorded, str(r.flock.batch_number), r.quantity, r.cause] for r in records]
    return _export_to_excel(rows, ["Date", "Flock", "Quantity", "Cause"], "mortality_report")


@login_required
def export_sales_excel(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)
    records = SalesRecord.objects.filter(date_sold__gte=month_ago)
    rows = [[r.date_sold, r.product, str(r.buyer), r.quantity, float(r.total_amount)] for r in records]
    return _export_to_excel(rows, ["Date", "Product", "Buyer", "Quantity", "Total Amount"], "sales_report")


@login_required
def export_expense_excel(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)
    records = ExpenseRecord.objects.filter(expense_date__gte=month_ago)
    rows = [[r.expense_date, r.category, r.description, float(r.amount)] for r in records]
    return _export_to_excel(rows, ["Date", "Category", "Description", "Amount"], "expense_report")


@login_required
def export_inventory_excel(request):
    items = InventoryItem.objects.filter(is_active=True)
    rows = [[r.name, str(r.category), float(r.quantity), str(r.unit), str(r.expiration_date or "N/A")] for r in items]
    return _export_to_excel(rows, ["Name", "Category", "Quantity", "Unit", "Expiry"], "inventory_report")


@login_required
def export_profit_loss_excel(request):
    today = timezone.now().date()
    month_ago = today - timezone.timedelta(days=30)
    total_sales = SalesRecord.objects.filter(date_sold__gte=month_ago).aggregate(total=Sum("total_amount"))["total"] or 0
    total_expenses = ExpenseRecord.objects.filter(expense_date__gte=month_ago).aggregate(total=Sum("amount"))["total"] or 0
    profit_loss = total_sales - total_expenses
    rows = [["Total Sales", float(total_sales)], ["Total Expenses", float(total_expenses)], ["Net Profit/Loss", float(profit_loss)]]
    return _export_to_excel(rows, ["Metric", "Amount"], "profit_loss_report")
