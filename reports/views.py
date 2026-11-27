import os

import openpyxl
from accounts.access import admin_or_owner_required, internal_only
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from flocks.models import FlockBatch
from feeding.models import FeedingRecord
from medicine.models import MedicineRecord
from inventory.models import InventoryItem
from eggs.models import EggProduction
from deaths.models import DeathRecord
from sales.models import SalesRecord
from expenses.models import ExpenseRecord

from . import pdfs

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


# The circular badge shipped in static/ is used whenever a farm has no uploaded logo.
DEFAULT_LOGO_PATH = os.path.join(settings.STATICFILES_DIRS[0], "images", "farm-logo.png")
DEFAULT_LOGO_URL = f"{settings.STATIC_URL}images/farm-logo.png"


def _farm_context(request):
    """Farm branding + provenance shared by every print/PDF preview."""
    profile = getattr(request.user, "farm_profile", None)
    logo = getattr(profile, "logo", None) if profile is not None else None
    return {
        "farm_name": getattr(profile, "farm_name", "") or "Tambulig Poultry Farm",
        "farm_location": getattr(profile, "location", "") or "Tambulig, Zamboanga del Sur",
        "farm_logo_url": logo.url if logo else DEFAULT_LOGO_URL,
        "farm_logo_path": logo.path if logo else DEFAULT_LOGO_PATH,
        "prepared_by": request.user.get_full_name() or request.user.username,
        "generated_at": timezone.localtime(),
    }


def _pdf_url(name, start=None, end=None):
    """Export-PDF link that keeps the same period the preview is showing."""
    url = reverse(name)
    if start is not None and end is not None:
        url = f"{url}?start_date={start.isoformat()}&end_date={end.isoformat()}"
    return url


# One entry per report card on the hub: the live report plus its three outputs.
REPORT_CATALOG = (
    {
        "title": "Flocks Report",
        "description": "Active and historical flock batches, breeds, stages and bird counts.",
        "period": "Current flocks",
        "accent": "emerald",
        "farm_operations": True,
        "icon": "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
        "urls": ("reports:flocks_report", "reports:flocks_report_print", "reports:export_flocks_pdf", "reports:export_flocks_excel"),
    },
    {
        "title": "Feeding Report",
        "description": "Daily feed consumption logs by flock batch and feed type.",
        "period": "Last 30 days",
        "accent": "amber",
        "farm_operations": True,
        "icon": "M12 6v6m0 0v6m0-6h6m-6 0H6",
        "urls": ("reports:feeding_report", "reports:feeding_report_print", "reports:export_feeding_pdf", "reports:export_feeding_excel"),
    },
    {
        "title": "Production Report",
        "description": "Eggs collected by flock and day, split by grade.",
        "period": "Last 30 days",
        "accent": "emerald",
        "farm_operations": True,
        "icon": "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
        "urls": ("reports:production_report", "reports:production_report_print", "reports:export_production_pdf", "reports:export_production_excel"),
    },
    {
        "title": "Deaths Report",
        "description": "Mortality records, quantities and causes.",
        "period": "Last 30 days",
        "accent": "red",
        "farm_operations": True,
        "icon": "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z",
        "urls": ("reports:death_report", "reports:death_report_print", "reports:export_death_pdf", "reports:export_death_excel"),
    },
    {
        "title": "Medicine Report",
        "description": "Medicines, vaccines and vitamins administered to flocks.",
        "period": "Last 30 days",
        "accent": "teal",
        "farm_operations": True,
        "icon": "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
        "urls": ("reports:medicine_report", "reports:medicine_report_print", "reports:export_medicine_pdf", "reports:export_medicine_excel"),
    },
    {
        "title": "Sales Report",
        "description": "Sold products, buyers and collected amounts.",
        "period": "Last 30 days",
        "accent": "blue",
        "farm_operations": False,
        "icon": "M9.5 16.5V7.5h3.25a2.75 2.75 0 010 5.5H9.5M8 9.5h7.5M8 11.5h7.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
        "urls": ("reports:sales_report", "reports:sales_report_print", "reports:export_sales_pdf", "reports:export_sales_excel"),
    },
    {
        "title": "Expense Report",
        "description": "Spending by category, supplier and date.",
        "period": "Last 30 days",
        "accent": "amber",
        "farm_operations": False,
        "icon": "M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z",
        "urls": ("reports:expense_report", "reports:expense_report_print", "reports:export_expense_pdf", "reports:export_expense_excel"),
    },
    {
        "title": "Inventory Report",
        "description": "Stock on hand with low-stock and expiry alerts.",
        "period": "Current stock",
        "accent": "purple",
        "farm_operations": False,
        "icon": "M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4",
        "urls": ("reports:inventory_report", "reports:inventory_report_print", "reports:export_inventory_pdf", "reports:export_inventory_excel"),
    },
    {
        "title": "Profit & Loss",
        "description": "Revenue against expenses, with the net result.",
        "period": "Last 30 days",
        "accent": "teal",
        "farm_operations": False,
        "icon": "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
        "urls": ("reports:profit_loss_report", "reports:profit_loss_report_print", "reports:export_profit_loss_pdf", "reports:export_profit_loss_excel"),
    },
)


@internal_only
def reports_index(request):
    is_elevated = request.user.is_admin_user() or request.user.is_owner()
    reports = []
    for entry in REPORT_CATALOG:
        if not is_elevated and not entry["farm_operations"]:
            continue
        open_url, print_url, pdf_url, excel_url = entry["urls"]
        reports.append(
            {
                "title": entry["title"],
                "description": entry["description"],
                "period": entry["period"],
                "accent": entry["accent"],
                "icon": entry["icon"],
                "open_url": reverse(open_url),
                "print_url": reverse(print_url),
                "pdf_url": reverse(pdf_url),
                "excel_url": reverse(excel_url),
            }
        )
    return render(request, "reports/reports_index.html", {"reports": reports})


# --------------------------------------------------------------------------- #
#  Flocks (Farm Operations)
# --------------------------------------------------------------------------- #
def _flocks_context():
    today = timezone.now().date()
    records = FlockBatch.objects.all()
    active_batches = records.filter(status="active").count()
    initial_birds = records.aggregate(total=Sum("quantity"))["total"] or 0
    total_birds = records.filter(status="active").aggregate(total=Sum("current_quantity"))["total"] or 0
    return {
        "records": records,
        "active_batches": active_batches,
        "initial_birds": initial_birds,
        "total_birds": total_birds,
        "report_title": "Flocks Report",
        "report_subtitle": "Flock batches and active bird counts",
        "date_range": f"Current flocks as of {today:%B %d, %Y}",
    }


@internal_only
def flocks_report(request):
    return render(request, "reports/flocks_report.html", _flocks_context())


@internal_only
def flocks_report_print(request):
    ctx = {**_flocks_context(), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:flocks_report")
    ctx["pdf_url"] = reverse("reports:export_flocks_pdf")
    return render(request, "reports/flocks_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Feeding (Farm Operations)
# --------------------------------------------------------------------------- #
def _feeding_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()
    records = FeedingRecord.objects.filter(feeding_date__range=(start, end)).select_related("flock", "feed_item")
    total_feed_used = records.aggregate(total=Sum("quantity_used"))["total"] or 0
    return {
        "records": records,
        "total_feed_used": total_feed_used,
        "report_title": "Feeding Report",
        "report_subtitle": "Feed consumption summary by flock",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def feeding_report(request):
    return render(request, "reports/feeding_report.html", _feeding_context())


@internal_only
def feeding_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_feeding_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:feeding_report")
    ctx["print_url"] = reverse("reports:feeding_report_print")
    ctx["pdf_url"] = _pdf_url("reports:export_feeding_pdf", start, end)
    ctx["show_date_filter"] = True
    return render(request, "reports/feeding_print.html", ctx)


# --------------------------------------------------------------------------- #
#  Medicine (Farm Operations)
# --------------------------------------------------------------------------- #
def _medicine_context(start=None, end=None):
    if start is None or end is None:
        start, end = _period()
    records = MedicineRecord.objects.filter(date_administered__range=(start, end)).select_related("flock", "medicine_item")
    total_quantity_used = records.aggregate(total=Sum("quantity_used"))["total"] or 0
    return {
        "records": records,
        "total_quantity_used": total_quantity_used,
        "report_title": "Medicine Report",
        "report_subtitle": "Medicine, vaccine and vitamin administrations",
        "date_range": _range_label(start, end),
        "start_date": start,
        "end_date": end,
    }


@internal_only
def medicine_report(request):
    return render(request, "reports/medicine_report.html", _medicine_context())


@internal_only
def medicine_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_medicine_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:medicine_report")
    ctx["print_url"] = reverse("reports:medicine_report_print")
    ctx["pdf_url"] = _pdf_url("reports:export_medicine_pdf", start, end)
    ctx["show_date_filter"] = True
    return render(request, "reports/medicine_print.html", ctx)


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
    ctx["pdf_url"] = _pdf_url("reports:export_production_pdf", start, end)
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
    ctx["pdf_url"] = _pdf_url("reports:export_death_pdf", start, end)
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


@admin_or_owner_required
def sales_report(request):
    return render(request, "reports/sales_report.html", _sales_context())


@admin_or_owner_required
def sales_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_sales_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:sales_report")
    ctx["print_url"] = reverse("reports:sales_report_print")
    ctx["pdf_url"] = _pdf_url("reports:export_sales_pdf", start, end)
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


@admin_or_owner_required
def expense_report(request):
    return render(request, "reports/expense_report.html", _expense_context())


@admin_or_owner_required
def expense_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_expense_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:expense_report")
    ctx["print_url"] = reverse("reports:expense_report_print")
    ctx["pdf_url"] = _pdf_url("reports:export_expense_pdf", start, end)
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


@admin_or_owner_required
def inventory_report(request):
    return render(request, "reports/inventory_report.html", _inventory_context())


@admin_or_owner_required
def inventory_report_print(request):
    ctx = {**_inventory_context(), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:inventory_report")
    ctx["pdf_url"] = reverse("reports:export_inventory_pdf")
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


@admin_or_owner_required
def profit_loss_report(request):
    return render(request, "reports/profit_loss_report.html", _profit_loss_context())


@admin_or_owner_required
def profit_loss_report_print(request):
    start, end = _requested_period(request)
    ctx = {**_profit_loss_context(start, end), **_farm_context(request)}
    ctx["back_url"] = reverse("reports:profit_loss_report")
    ctx["print_url"] = reverse("reports:profit_loss_report_print")
    ctx["pdf_url"] = _pdf_url("reports:export_profit_loss_pdf", start, end)
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
def export_flocks_excel(request):
    records = _flocks_context()["records"]
    rows = [
        [r.batch_number, r.breed, r.get_growing_stage_display(), r.quantity, r.remaining_stock(), r.date_acquired, r.get_status_display()]
        for r in records
    ]
    return _export_to_excel(rows, ["Batch", "Breed", "Stage", "Initial Qty", "Current Qty", "Date Acquired", "Status"], "flocks_report")


@internal_only
def export_feeding_excel(request):
    records = _feeding_context()["records"]
    rows = [
        [r.feeding_date, str(r.flock.batch_number), str(r.feed_item.name), float(r.quantity_used), r.remarks or ""]
        for r in records
    ]
    return _export_to_excel(rows, ["Date", "Flock", "Feed Item", "Quantity Used", "Remarks"], "feeding_report")


@internal_only
def export_medicine_excel(request):
    records = _medicine_context()["records"]
    rows = [
        [r.date_administered, str(r.flock.batch_number), r.get_medicine_type_display(), r.medicine_name, r.dosage, r.get_administration_route_display(), str(r.next_schedule or "")]
        for r in records
    ]
    return _export_to_excel(rows, ["Date", "Flock", "Type", "Medicine", "Dosage", "Route", "Next Schedule"], "medicine_report")


@internal_only
def export_production_excel(request):
    records = _production_context()["records"]
    rows = [[r.production_date, str(r.flock.batch_number), r.total_eggs, r.good_eggs, r.cracked_eggs, r.rejected_eggs] for r in records]
    return _export_to_excel(rows, ["Date", "Flock", "Total Eggs", "Good", "Cracked", "Rejected"], "production_report")


@internal_only
def export_death_excel(request):
    records = _death_context()["records"]
    rows = [[r.date_recorded, str(r.flock.batch_number), r.quantity, r.cause_of_death] for r in records]
    return _export_to_excel(rows, ["Date", "Flock", "Quantity", "Cause"], "death_report")


@admin_or_owner_required
def export_sales_excel(request):
    records = _sales_context()["records"]
    rows = [[r.date_sold, r.product_name, str(r.buyer), r.quantity, float(r.total_amount)] for r in records]
    return _export_to_excel(rows, ["Date", "Product", "Buyer", "Quantity", "Total Amount"], "sales_report")


@admin_or_owner_required
def export_expense_excel(request):
    records = _expense_context()["records"]
    rows = [[r.expense_date, str(r.category), r.description, float(r.amount)] for r in records]
    return _export_to_excel(rows, ["Date", "Category", "Description", "Amount"], "expense_report")


@admin_or_owner_required
def export_inventory_excel(request):
    items = _inventory_context()["items"]
    rows = [[r.name, str(r.category), float(r.quantity), str(r.unit), str(r.expiration_date or "N/A")] for r in items]
    return _export_to_excel(rows, ["Name", "Category", "Quantity", "Unit", "Expiry"], "inventory_report")


@admin_or_owner_required
def export_profit_loss_excel(request):
    ctx = _profit_loss_context()
    rows = [
        ["Total Sales", float(ctx["total_sales"])],
        ["Total Expenses", float(ctx["total_expenses"])],
        ["Net Profit/Loss", float(ctx["profit_loss"])],
    ]
    return _export_to_excel(rows, ["Metric", "Amount"], "profit_loss_report")


# --------------------------------------------------------------------------- #
#  PDF exports - a downloadable file, kept separate from the print previews
# --------------------------------------------------------------------------- #
@internal_only
def export_flocks_pdf(request):
    ctx = {**_flocks_context(), **_farm_context(request)}
    return pdfs.response("flocks", ctx)


@internal_only
def export_feeding_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_feeding_context(start, end), **_farm_context(request)}
    return pdfs.response("feeding", ctx)


@internal_only
def export_medicine_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_medicine_context(start, end), **_farm_context(request)}
    return pdfs.response("medicine", ctx)


@internal_only
def export_production_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_production_context(start, end), **_farm_context(request)}
    return pdfs.response("production", ctx)


@internal_only
def export_death_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_death_context(start, end), **_farm_context(request)}
    return pdfs.response("deaths", ctx)


@admin_or_owner_required
def export_sales_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_sales_context(start, end), **_farm_context(request)}
    return pdfs.response("sales", ctx)


@admin_or_owner_required
def export_expense_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_expense_context(start, end), **_farm_context(request)}
    return pdfs.response("expenses", ctx)


@admin_or_owner_required
def export_inventory_pdf(request):
    ctx = {**_inventory_context(), **_farm_context(request)}
    return pdfs.response("inventory", ctx)


@admin_or_owner_required
def export_profit_loss_pdf(request):
    start, end = _requested_period(request)
    ctx = {**_profit_loss_context(start, end), **_farm_context(request)}
    return pdfs.response("profit-loss", ctx)
