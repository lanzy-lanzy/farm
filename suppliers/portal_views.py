from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.access import external_portal_required
from config.htmx import is_htmx, modal_closed
from notifications.utils import notify_team

from .forms import (
    DeliveryNoticeForm,
    FarmOrderResponseForm,
    SupplierProfileForm,
    SupplyItemForm,
)
from .models import DeliveryNotice, SupplyItem


def _supplier(request):
    return request.user.supplier


def _open_catalog_modal(kind, pk=None):
    """Full-page fallback: send plain GETs back to the unified catalog page, which opens the modal."""
    path = reverse("portal:supplier_catalog")
    if kind == "add":
        return redirect(f"{path}?add=1")
    return redirect(f"{path}?edit={pk}")


@external_portal_required("supplier")
def supplier_home(request):
    supplier = _supplier(request)
    catalog = supplier.supply_items.filter(is_active=True)
    notices = supplier.delivery_notices.all()[:5]
    open_deliveries = supplier.delivery_notices.filter(status__in=["announced", "confirmed"]).count()
    farm_orders = supplier.delivery_notices.filter(origin="farm", status="announced")[:3]
    inactive_items = supplier.supply_items.filter(is_active=False).count()
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
            "open_deliveries": open_deliveries,
            "farm_orders": farm_orders,
            "inactive_items": inactive_items,
            "month_total": month_total,
        },
    )


@external_portal_required("supplier")
def catalog_list(request):
    supplier = _supplier(request)
    items = supplier.supply_items.all()
    context = {
        "supplier": supplier,
        "items": items,
        "inactive_items": supplier.supply_items.filter(is_active=False).count(),
        "modal_form": None,
        "modal_item": None,
    }
    # ?add=1 and ?edit=<pk> come from the sidebar and the dashboard. Rendering the dialog
    # server-side (instead of fetching it on page load) keeps it open deterministically.
    if request.GET.get("add") == "1":
        context["modal_form"] = SupplyItemForm()
    else:
        edit_pk = request.GET.get("edit", "")
        if edit_pk.isdigit():
            context["modal_item"] = get_object_or_404(SupplyItem, pk=edit_pk, supplier=supplier)
            context["modal_form"] = SupplyItemForm(instance=context["modal_item"])
    return render(request, "portal/supplier/catalog_list.html", context)


@external_portal_required("supplier")
def catalog_detail(request, pk):
    """Read side of the catalog CRUD — rendered as a modal fragment on the unified page."""
    supplier = _supplier(request)
    item = get_object_or_404(SupplyItem, pk=pk, supplier=supplier)
    if not is_htmx(request):
        return redirect("portal:supplier_catalog")
    return render(
        request, "portal/supplier/_catalog_detail.html", {"supplier": supplier, "item": item}
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
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:supplier_catalog")
    else:
        if not is_htmx(request):
            return _open_catalog_modal("add")
        form = SupplyItemForm()
    return render(
        request, "portal/supplier/_catalog_form.html", {"supplier": supplier, "form": form}
    )


@external_portal_required("supplier")
def catalog_update(request, pk):
    supplier = _supplier(request)
    item = get_object_or_404(SupplyItem, pk=pk, supplier=supplier)
    if request.method == "POST":
        form = SupplyItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{item.name}' updated.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:supplier_catalog")
    else:
        if not is_htmx(request):
            return _open_catalog_modal("edit", item.pk)
        form = SupplyItemForm(instance=item)
    return render(
        request,
        "portal/supplier/_catalog_form.html",
        {"supplier": supplier, "form": form, "item": item},
    )


@external_portal_required("supplier")
def catalog_delete(request, pk):
    supplier = _supplier(request)
    item = get_object_or_404(SupplyItem, pk=pk, supplier=supplier)
    if request.method == "POST":
        name = item.name
        item.delete()
        messages.success(request, f"'{name}' removed from your catalog.")
        if is_htmx(request):
            return modal_closed()
        return redirect("portal:supplier_catalog")
    if not is_htmx(request):
        return redirect("portal:supplier_catalog")
    return render(
        request, "portal/supplier/_catalog_delete.html", {"supplier": supplier, "item": item}
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
                f"{notice.quantity_label} expected on {notice.expected_date}.",
                link="/expenses/deliveries/",
                target=f"delivery_notice:{notice.pk}",
            )
            messages.success(request, "Delivery notice sent to the farm.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:supplier_deliveries")
    else:
        form = DeliveryNoticeForm(supplier=supplier)
    template = (
        "portal/supplier/_delivery_form.html"
        if is_htmx(request)
        else "portal/supplier/delivery_form.html"
    )
    return render(request, template, {"supplier": supplier, "form": form})


@external_portal_required("supplier")
def delivery_notice_cancel(request, pk):
    """Supplier withdraws their own announced notice so it stops occupying the farm queue."""
    supplier = _supplier(request)
    notice = get_object_or_404(DeliveryNotice, pk=pk, supplier=supplier)
    if request.method == "POST":
        if not notice.is_supplier_cancellable:
            messages.error(request, "Only your own announced deliveries can be cancelled.")
        else:
            notice.status = "rejected"
            notice.supplier_note = request.POST.get("note", "").strip() or notice.supplier_note
            notice.save()
            notify_team(
                "delivery_notice",
                f"Delivery cancelled: {notice.description}",
                f"{supplier.name} cancelled the announced delivery. "
                + (notice.supplier_note or ""),
                link="/expenses/deliveries/",
                target=f"delivery_notice:{notice.pk}",
            )
            messages.success(request, "Delivery announcement cancelled.")
        if is_htmx(request):
            return modal_closed()
        return redirect("portal:supplier_deliveries")
    if not is_htmx(request):
        return redirect("portal:supplier_deliveries")
    return render(
        request, "portal/supplier/_delivery_cancel.html", {"supplier": supplier, "notice": notice}
    )


@external_portal_required("supplier")
def delivery_notice_respond(request, pk):
    """Supplier confirms or adjusts the expected date / note on a farm-ordered delivery."""
    supplier = _supplier(request)
    notice = get_object_or_404(DeliveryNotice, pk=pk, supplier=supplier)
    if request.method == "POST":
        if not notice.can_supplier_respond:
            messages.error(request, "This farm order can no longer be updated.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:supplier_deliveries")
        form = FarmOrderResponseForm(request.POST, instance=notice)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.status = "confirmed"
            notice.save()
            notify_team(
                "delivery_notice",
                f"Supplier confirmed delivery: {notice.description}",
                f"{supplier.name} confirmed the farm order for {notice.expected_date}."
                + (f" Note: {notice.supplier_note}" if notice.supplier_note else ""),
                link="/expenses/deliveries/",
                target=f"delivery_notice:{notice.pk}",
            )
            messages.success(request, "Delivery date confirmed — the farm has been notified.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:supplier_deliveries")
    else:
        if not is_htmx(request):
            return redirect("portal:supplier_deliveries")
        form = FarmOrderResponseForm(instance=notice)
    return render(
        request,
        "portal/supplier/_delivery_respond.html",
        {"supplier": supplier, "notice": notice, "form": form},
    )


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
    items = supplier.supply_items
    notices = supplier.delivery_notices
    return render(
        request,
        "portal/supplier/profile.html",
        {
            "supplier": supplier,
            "active_items": items.filter(is_active=True).count(),
            "total_items": items.count(),
            "received_notices": notices.filter(status="received").count(),
            "total_notices": notices.count(),
        },
    )


@external_portal_required("supplier")
def supplier_profile_update(request):
    supplier = _supplier(request)
    if request.method == "POST":
        form = SupplierProfileForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:supplier_profile")
    else:
        if not is_htmx(request):
            return redirect("portal:supplier_profile")
        form = SupplierProfileForm(instance=supplier)
    return render(
        request, "portal/supplier/_profile_form.html", {"supplier": supplier, "form": form}
    )
