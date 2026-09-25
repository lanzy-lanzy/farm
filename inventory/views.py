from urllib.parse import urlencode

from django.contrib import messages
from accounts.access import internal_only
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from reports.views import _farm_context
from .forms import InventoryItemForm, InventoryTransactionForm, InventoryCategoryForm, UnitForm
from .models import InventoryItem, InventoryTransaction, InventoryCategory, Unit
from notifications.utils import check_and_notify_inventory, log_activity
from suppliers.models import Supplier


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


# Rows per page on the on-screen list; the print/PDF view never paginates.
INVENTORY_PAGE_SIZE = 20

# Maps the ?status= value to a human label for the print subtitle.
STATUS_LABELS = {"in_stock": "In Stock", "low_stock": "Low Stock", "expired": "Expired"}


def _filtered_inventory(request):
    """Active inventory narrowed by the list's search / category / status bar.

    Returns ``(items, params)``. Shared by the paginated list and the print/PDF
    view, so both always agree on exactly which rows are in scope. Expired takes
    precedence over low stock, matching the badges the table shows.
    """
    items = InventoryItem.objects.filter(is_active=True).select_related(
        "category", "unit", "supplier"
    )
    today = timezone.now().date()
    expired_q = Q(expiration_date__isnull=False, expiration_date__lte=today)
    low_q = Q(quantity__lte=F("reorder_level"))

    search = request.GET.get("search", "").strip()
    category = request.GET.get("category", "")
    status = request.GET.get("status", "")

    if search:
        items = items.filter(name__icontains=search)
    if category:
        items = items.filter(category_id=category)
    if status == "expired":
        items = items.filter(expired_q)
    elif status == "low_stock":
        items = items.filter(low_q & ~expired_q)
    elif status == "in_stock":
        items = items.filter(~low_q & ~expired_q)

    params = {
        "search": search,
        "category": category,
        "status": status,
        "has_filters": bool(search or category or status),
    }
    return items, params


def _inventory_stats(items):
    """Headline totals for an already-filtered queryset (low excludes expired)."""
    today = timezone.now().date()
    expired_q = Q(expiration_date__isnull=False, expiration_date__lte=today)
    low_q = Q(quantity__lte=F("reorder_level"))
    total_value = items.aggregate(v=Sum(F("quantity") * F("cost_per_unit")))["v"] or 0
    return {
        "stat_total": items.count(),
        "stat_low_stock": items.filter(low_q & ~expired_q).count(),
        "stat_expired": items.filter(expired_q).count(),
        "stat_total_value": total_value,
    }


@internal_only
def inventory_list(request):
    items, params = _filtered_inventory(request)
    paginator = Paginator(items, INVENTORY_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    categories = InventoryCategory.objects.all()
    # Query string without the page number, so pagination and print keep filters.
    query = urlencode({k: v for k, v in params.items() if v and k != "has_filters"})
    context = {
        "items": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "categories": categories,
        "query": query,
        "print_url": reverse("inventory:inventory_print") + (f"?{query}" if query else ""),
        **params,
        **_inventory_stats(items),
    }
    return render(request, "inventory/inventory_list.html", context)


@internal_only
def inventory_print(request):
    """Standalone, filter-aware print preview: the source for Print / Save as PDF."""
    items, params = _filtered_inventory(request)
    today = timezone.now().date()
    scope = "Complete on-hand inventory snapshot"
    if params["has_filters"]:
        parts = []
        if params["search"]:
            parts.append(f"name matching \u201c{params['search']}\u201d")
        if params["category"]:
            cat = InventoryCategory.objects.filter(pk=params["category"]).first()
            if cat:
                parts.append(f"category {cat.name}")
        if params["status"]:
            parts.append(f"status {STATUS_LABELS.get(params['status'], params['status'])}")
        scope = "Filtered inventory (" + ", ".join(parts) + ")"
    context = {
        "items": items,
        "report_title": "Inventory List",
        "report_subtitle": scope,
        "date_range": f"{today:%B %d, %Y}",  # base prints it under a "Period:" label
        "back_url": reverse("inventory:inventory_list"),
        **_inventory_stats(items),
        **_farm_context(request),
    }
    return render(request, "inventory/inventory_print.html", context)


@internal_only
def inventory_detail(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    transactions = InventoryTransaction.objects.filter(item=item)[:20]
    return render(
        request, "inventory/inventory_detail.html", {"item": item, "transactions": transactions}
    )


@internal_only
def inventory_create(request):
    categories = InventoryCategory.objects.all()
    units = Unit.objects.all()
    suppliers_list = Supplier.objects.filter(is_active=True)
    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()
            log_activity(request.user, "create", "InventoryItem", item.pk, item.name, "Created inventory item")
            check_and_notify_inventory(item, request)
            messages.success(request, "Inventory item created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("inventory:inventory_list")
    else:
        form = InventoryItemForm()
    template = "inventory/_form.html" if is_htmx(request) else "inventory/inventory_form.html"
    return render(request, template, {"form": form, "categories": categories, "units": units, "suppliers": suppliers_list})


@internal_only
def inventory_update(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    categories = InventoryCategory.objects.all()
    units = Unit.objects.all()
    suppliers_list = Supplier.objects.filter(is_active=True)
    if request.method == "POST":
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "InventoryItem", item.pk, item.name, "Updated inventory item")
            check_and_notify_inventory(item, request)
            messages.success(request, "Inventory item updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("inventory:inventory_list")
    else:
        form = InventoryItemForm(instance=item)
    template = "inventory/_form.html" if is_htmx(request) else "inventory/inventory_form.html"
    return render(request, template, {"form": form, "item": item, "categories": categories, "units": units, "suppliers": suppliers_list})


@internal_only
def inventory_delete(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "InventoryItem", item.pk, item.name, "Deleted inventory item")
        item.delete()
        messages.success(request, "Inventory item deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("inventory:inventory_list")
    template = "inventory/_delete.html" if is_htmx(request) else "inventory/inventory_confirm_delete.html"
    return render(request, template, {"item": item})


@internal_only
def transaction_create(request, item_id=None):
    item = None
    if item_id:
        item = get_object_or_404(InventoryItem, pk=item_id)
    if request.method == "POST":
        form = InventoryTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.save()
            messages.success(request, "Transaction recorded successfully.")
            if item:
                return redirect("inventory:inventory_detail", pk=item.pk)
            return redirect("inventory:inventory_list")
    else:
        form = InventoryTransactionForm(initial={"item": item})
    return render(
        request, "inventory/transaction_form.html", {"form": form, "item": item}
    )


@internal_only
def category_list(request):
    categories = InventoryCategory.objects.all()
    return render(request, "inventory/category_list.html", {"categories": categories})


@internal_only
def category_create(request):
    if request.method == "POST":
        form = InventoryCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully.")
            return redirect("inventory:category_list")
    else:
        form = InventoryCategoryForm()
    return render(request, "inventory/category_form.html", {"form": form})


@internal_only
def unit_list(request):
    units = Unit.objects.all()
    return render(request, "inventory/unit_list.html", {"units": units})


@internal_only
def unit_create(request):
    if request.method == "POST":
        form = UnitForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Unit created successfully.")
            return redirect("inventory:unit_list")
    else:
        form = UnitForm()
    return render(request, "inventory/unit_form.html", {"form": form})
