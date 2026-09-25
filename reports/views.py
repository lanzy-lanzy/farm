import openpyxl
from accounts.access import internal_only
from django.db import models
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from flocks.models import FlockBatch
from inventory.models import InventoryItem
from eggs.models import EggProduction
from deaths.models import DeathRecord
from sales.models import SalesRecord
from expenses.models import ExpenseRecord

# Reports default to a rolling 30-day window.
REPORT_DAYS = 30


def _period(days=REPORT_DAYS):
    """Return (start_date, today) for the rolling report window."""
    today = timezone.now().date()
    return today - timezone.timedelta(days=days), today


def _range_label(start, today):
    return f"{start:%B %d, %Y} \u2013 {today:%B %d, %Y}"


def _parse_date_or_none(value):
    """Parse an ISO ``YYYY-MM-DD`` string, returning ``None`` on any failure.

    ``parse_date`` returns ``None`` for non-numeric formats but raises
    ``ValueError`` for structurally-valid yet out-of-range values (e.g. month
    13), so normalise both cases to ``None``.
    """
    if not value:
        return None
    try:
        return parse_date(value)
    except (ValueError, TypeError):
        return None


def _requested_period(request):
    """Resolve an effective (start, end) window from ?start_date=&end_date=.

    Dates must be ISO ``YYYY-MM-DD`` and ``start_date <= end_date``. When the
    parameters are missing, malformed, or inverted we fall back to the default
    rolling window so the print view always renders something valid.
    """
    default_start, default_end = _period()
    start = _parse_date_or_none(request.GET.get("start_date"))
    end = _parse_date_or_none(request.GET.get("end_date"))
    if start is None or end is None or start > end:
        return default_start, default_end
    return start, end


def _farm_context(request):
    """Farm branding + provenance shared by every print/PDF preview."""
    profile = getattr(request.user, "farm_profile", None)
    logo_url = None
    if profile is not None and getattr(profile, "logo", None):
        logo_url = profile.logo.url
    return {
        "farm_name": getattr(profile, "farm_name", "") or "Tambulig Poultry Farm",
        "farm_location": getattr(profile, "location", "") or "Tambulig, Zamboanga del Sur",
        "farm_logo_url": logo_url,
        "prepared_by": request.user.get_full_name() or request.user.username,
        "generated_at": timezone.localtime(),
    }


@internal_only
def reports_index(request):
    return render(request, "reports/reports_index.html")


# --------------------------------------------------------------------------- #
#  Production
# --------------------------------------------------------------------------- #
def _production_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()
    records = EggProduction.objects.filter(production_date__range=(start, end))
    agg = records.aggregate(
        eggs=Sum("total_eggs"),
        good=Sum("good_eggs"),
        cracked=Sum("cracked_eggs"),
        rejected=Sum("rejected_eggs"),
    )
    return {
        "records": records,
        "total_eggs": agg["eggs"] or 0,
        "total_good": agg["good"] or 0,
        "total_cracked": agg["cracked"] or 0,
        "total_rejected": agg["rejected"] or 0,
        "report_title": "Production Report",
        "report_subtitle": "Egg production summary",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def production_report(request):
    return render(request, "reports/production_report.html", _production_context())


@internal_only
def production_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_production_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:production_report")
    ctx["print_url"] = reverse("reports:production_report_print")
    ctx["show_date_filter"] = True
    return render(request, "reports/production_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Deaths
# --------------------------------------------------------------------------- #
def _death_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()
    records = DeathRecord.objects.filter(date_recorded__range=(start, end))
    total_mortality = records.aggregate(total=Sum("quantity"))["total"] or 0
    return {
        "records": records,
        "total_mortality": total_mortality,
        "report_title": "Deaths Report",
        "report_subtitle": "Death records and causes",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def death_report(request):
    return render(request, "reports/death_report.html", _death_context())


@internal_only
def death_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_death_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:death_report")
    ctx["print_url"] = reverse("reports:death_report_print")
    ctx["show_date_filter"] = True
    return render(request, "reports/death_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Sales
# --------------------------------------------------------------------------- #
def _sales_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()
    records = SalesRecord.objects.filter(date_sold__range=(start, end))
    total_sales = records.aggregate(total=Sum("total_amount"))["total"] or 0
    return {
        "records": records,
        "total_sales": total_sales,
        "report_title": "Sales Report",
        "report_subtitle": "Sales transactions",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def sales_report(request):
    return render(request, "reports/sales_report.html", _sales_context())


@internal_only
def sales_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_sales_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:sales_report")
    ctx["print_url"] = reverse("reports:sales_report_print")
    ctx["show_date_filter"] = True
    return render(request, "reports/sales_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Expenses
# --------------------------------------------------------------------------- #
def _expense_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()
    records = ExpenseRecord.objects.filter(expense_date__range=(start, end))
    total_expenses = records.aggregate(total=Sum("amount"))["total"] or 0
    return {
        "records": records,
        "total_expenses": total_expenses,
        "report_title": "Expense Report",
        "report_subtitle": "Farm expenses breakdown",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def expense_report(request):
    return render(request, "reports/expense_report.html", _expense_context())


@internal_only
def expense_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_expense_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:expense_report")
    ctx["print_url"] = reverse("reports:expense_report_print")
    ctx["show_date_filter"] = True
    return render(request, "reports/expense_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Inventory
# --------------------------------------------------------------------------- #
def _inventory_context():
    today = timezone.now().date()
    items = InventoryItem.objects.filter(is_active=True)
    low_stock = items.filter(quantity__lte=models.F("reorder_level"))
    expired = items.filter(
        expiration_date__lte=today, expiration_date__isnull=False
    )
    return {
        "items": items,
        "low_stock": low_stock,
        "expired": expired,
        "report_title": "Inventory Report",
        "report_subtitle": "Stock levels and alerts",
        "date_range": f"Current stock as of {today:%B %d, %Y}",
    }


@internal_only
def inventory_report(request):
    return render(request, "reports/inventory_report.html", _inventory_context())


@internal_only
def inventory_report_print(request):
    ctx = {**_inventory_context(), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:inventory_report")
    return render(request, "reports/inventory_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Profit & Loss
# --------------------------------------------------------------------------- #
def _profit_loss_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()

    total_sales = SalesRecord.objects.filter(
        date_sold__range=(start, end)
    ).aggregate(total=Sum("total_amount"))["total"] or 0

    total_expenses = ExpenseRecord.objects.filter(
        expense_date__range=(start, end)
    ).aggregate(total=Sum("amount"))["total"] or 0

    profit_loss = total_sales - total_expenses
    margin_pct = (profit_loss / total_sales * 100) if total_sales else None

    return {
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "profit_loss": profit_loss,
        "margin_pct": margin_pct,
        "margin_display": f"{margin_pct:.1f}%" if margin_pct is not None else "N/A",
        "report_title": "Profit & Loss Report",
        "report_subtitle": "Financial summary",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def profit_loss_report(request):
    return render(request, "reports/profit_loss_report.html", _profit_loss_context())


@internal_only
def profit_loss_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_profit_loss_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:profit_loss_report")
    ctx["print_url"] = reverse("reports:profit_loss_report_print")
    ctx["show_date_filter"] = True
    return render(request, "reports/profit_loss_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Excel exports (unchanged behaviour, reuse the same query helpers)
# --------------------------------------------------------------------------- #
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


@internal_only
def export_production_excel(request):
    records = _production_context()["records"]
    rows = [[r.production_date, str(r.flock.batch_number), r.total_eggs, r.good_eggs, r.cracked_eggs, r.rejected_eggs] for r in records]
    return _export_to_excel(rows, ["Date", "Flock", "Total Eggs", "Good", "Cracked", "Rejected"], "production_report")


@internal_only
def export_death_excel(request):
    records = _death_context()["records"]
    rows = [[r.date_recorded, str(r.flock.batch_number), r.quantity, r.cause] for r in records]
    return _export_to_excel(rows, ["Date", "Flock", "Quantity", "Cause"], "death_report")


@internal_only
def export_sales_excel(request):
    records = _sales_context()["records"]
    rows = [[r.date_sold, r.product, str(r.buyer), r.quantity, float(r.total_amount)] for r in records]
    return _export_to_excel(rows, ["Date", "Product", "Buyer", "Quantity", "Total Amount"], "sales_report")


@internal_only
def export_expense_excel(request):
    records = _expense_context()["records"]
    rows = [[r.expense_date, r.category, r.description, float(r.amount)] for r in records]
    return _export_to_excel(rows, ["Date", "Category", "Description", "Amount"], "expense_report")


@internal_only
def export_inventory_excel(request):
    items = _inventory_context()["items"]
    rows = [[r.name, str(r.category), float(r.quantity), str(r.unit), str(r.expiration_date or "N/A")] for r in items]
    return _export_to_excel(rows, ["Name", "Category", "Quantity", "Unit", "Expiry"], "inventory_report")


@internal_only
def export_profit_loss_excel(request):
    ctx = _profit_loss_context()
    rows = [
        ["Total Sales", float(ctx["total_sales"])],
        ["Total Expenses", float(ctx["total_expenses"])],
        ["Net Profit/Loss", float(ctx["profit_loss"])],
    ]
    return _export_to_excel(rows, ["Metric", "Amount"], "profit_loss_report")
