from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import InventoryItemForm, InventoryTransactionForm, InventoryCategoryForm, UnitForm
from .models import InventoryItem, InventoryTransaction, InventoryCategory, Unit
from notifications.utils import check_and_notify_inventory, log_activity
from suppliers.models import Supplier


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def inventory_list(request):
    items = InventoryItem.objects.filter(is_active=True)
    category_filter = request.GET.get("category", "")
    if category_filter:
        items = items.filter(category_id=category_filter)
    categories = InventoryCategory.objects.all()
    return render(
        request,
        "inventory/inventory_list.html",
        {"items": items, "categories": categories, "category_filter": category_filter},
    )


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
