from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.access import external_portal_required
from notifications.utils import notify_team

from .forms import DeliveryNoticeForm, SupplierProfileForm, SupplyItemForm
from .models import DeliveryNotice, SupplyItem


def _supplier(request):
    return request.user.supplier


@external_portal_required("supplier")
def supplier_home(request):
    supplier = _supplier(request)
    catalog = supplier.supply_items.filter(is_active=True)
    notices = supplier.delivery_notices.all()[:5]
    announced = supplier.delivery_notices.filter(status="announced").count()
    month_start = timezone.localdate().replace(day=1)
    month_total = supplier.expense_records.filter(
        expense_date__gte=month_start
    ).aggregate(total=Sum("amount"))["total"] or 0
    return render(
        request,
        "portal/supplier/home.html",
        {
            "supplier": supplier,
            "catalog": catalog,
            "notices": notices,
            "announced": announced,
            "month_total": month_total,
        },
    )


@external_portal_required("supplier")
def catalog_list(request):
    supplier = _supplier(request)
    items = supplier.supply_items.all()
    return render(
        request, "portal/supplier/catalog_list.html", {"supplier": supplier, "items": items}
    )


@external_portal_required("supplier")
def catalog_create(request):
    supplier = _supplier(request)
    if request.method == "POST":
        form = SupplyItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.supplier = supplier
            item.save()
            messages.success(request, f"'{item.name}' added to your catalog.")
            return redirect("portal:supplier_catalog")
    else:
        form = SupplyItemForm()
    return render(
        request, "portal/supplier/catalog_form.html", {"supplier": supplier, "form": form}
    )


@external_portal_required("supplier")
def catalog_update(request, pk):
    supplier = _supplier(request)
    item = get_object_or_404(SupplyItem, pk=pk, supplier=supplier)
    if request.method == "POST":
        form = SupplyItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated.")
            return redirect("portal:supplier_catalog")
    else:
        form = SupplyItemForm(instance=item)
    return render(
        request,
        "portal/supplier/catalog_form.html",
        {"supplier": supplier, "form": form, "item": item},
    )


@external_portal_required("supplier")
def catalog_delete(request, pk):
    supplier = _supplier(request)
    item = get_object_or_404(SupplyItem, pk=pk, supplier=supplier)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Item removed.")
        return redirect("portal:supplier_catalog")
    return render(
        request, "portal/supplier/catalog_confirm_delete.html", {"supplier": supplier, "item": item}
    )


@external_portal_required("supplier")
def delivery_notice_list(request):
    supplier = _supplier(request)
    notices = supplier.delivery_notices.all()
    return render(
        request, "portal/supplier/deliveries_list.html", {"supplier": supplier, "notices": notices}
    )


@external_portal_required("supplier")
def delivery_notice_create(request):
    supplier = _supplier(request)
    if request.method == "POST":
        form = DeliveryNoticeForm(request.POST, supplier=supplier)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.supplier = supplier
            notice.save()
            notify_team(
                "delivery_notice",
                f"Delivery from {supplier.name}",
                f"{notice.quantity} {notice.description} expected on {notice.expected_date}.",
                link="/expenses/deliveries/",
            )
            messages.success(request, "Delivery notice sent to the farm.")
            return redirect("portal:supplier_deliveries")
    else:
        form = DeliveryNoticeForm(supplier=supplier)
    return render(
        request, "portal/supplier/delivery_form.html", {"supplier": supplier, "form": form}
    )


@external_portal_required("supplier")
def delivery_notice_cancel(request, pk):
    """Supplier withdraws their own announced notice so it stops occupying the farm queue."""
    supplier = _supplier(request)
    notice = get_object_or_404(DeliveryNotice, pk=pk, supplier=supplier)
    if request.method != "POST":
        return redirect("portal:supplier_deliveries")
    if not notice.is_supplier_cancellable:
        messages.error(request, "Only your own announced deliveries can be cancelled.")
        return redirect("portal:supplier_deliveries")
    notice.status = "rejected"
    notice.supplier_note = request.POST.get("note", "").strip() or notice.supplier_note
    notice.save()
    notify_team(
        "delivery_notice",
        f"Delivery cancelled: {notice.description}",
        f"{supplier.name} cancelled the announced delivery. "
        + (notice.supplier_note or ""),
        link="/expenses/deliveries/",
    )
    messages.success(request, "Delivery announcement cancelled.")
    return redirect("portal:supplier_deliveries")


@external_portal_required("supplier")
def delivery_notice_respond(request, pk):
    """Supplier confirms or adjusts the expected date / note on a farm-ordered delivery."""
    supplier = _supplier(request)
    notice = get_object_or_404(DeliveryNotice, pk=pk, supplier=supplier)
    if request.method != "POST":
        return redirect("portal:supplier_deliveries")
    if not notice.is_farm_order_open:
        messages.error(request, "This farm order can no longer be updated.")
        return redirect("portal:supplier_deliveries")
    from .forms import FarmOrderResponseForm

    form = FarmOrderResponseForm(request.POST, instance=notice)
    if form.is_valid():
        form.save()
        notify_team(
            "delivery_notice",
            f"Supplier confirmed delivery: {notice.description}",
            f"{supplier.name} confirmed the farm order for {notice.expected_date}."
            + (f" Note: {notice.supplier_note}" if notice.supplier_note else ""),
            link="/expenses/deliveries/",
        )
        messages.success(request, "Delivery date confirmed — the farm has been notified.")
    return redirect("portal:supplier_deliveries")


@external_portal_required("supplier")
def purchase_history(request):
    supplier = _supplier(request)
    records = supplier.expense_records.all()
    month = request.GET.get("month", "")
    if len(month) == 7 and month.replace("-", "").isdigit():
        year, mon = month.split("-")
        records = records.filter(expense_date__year=int(year), expense_date__month=int(mon))
    total = records.aggregate(total=Sum("amount"))["total"] or 0
    return render(
        request,
        "portal/supplier/history.html",
        {"supplier": supplier, "records": records, "total": total, "month": month},
    )


@external_portal_required("supplier")
def supplier_profile(request):
    supplier = _supplier(request)
    if request.method == "POST":
        form = SupplierProfileForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("portal:supplier_home")
    else:
        form = SupplierProfileForm(instance=supplier)
    return render(
        request, "portal/supplier/profile.html", {"supplier": supplier, "form": form}
    )
