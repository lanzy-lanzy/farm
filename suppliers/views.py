from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import SupplierForm
from .models import Supplier
from accounts.access import admin_or_owner_required, create_portal_account
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def supplier_list(request):
    suppliers = Supplier.objects.all()
    return render(request, "suppliers/supplier_list.html", {"suppliers": suppliers})


@internal_only
def supplier_create(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.created_by = request.user
            supplier.save()
            log_activity(request.user, "create", "Supplier", supplier.pk, supplier.__str__(), "Created supplier")
            messages.success(request, "Supplier created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("suppliers:supplier_list")
    else:
        form = SupplierForm()
    template = "suppliers/_form.html" if is_htmx(request) else "suppliers/supplier_form.html"
    return render(request, template, {"form": form})


@internal_only
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "Supplier", supplier.pk, supplier.__str__(), "Updated supplier")
            messages.success(request, "Supplier updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("suppliers:supplier_list")
    else:
        form = SupplierForm(instance=supplier)
    template = "suppliers/_form.html" if is_htmx(request) else "suppliers/supplier_form.html"
    return render(request, template, {"form": form, "supplier": supplier})


@internal_only
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "Supplier", supplier.pk, supplier.__str__(), "Deleted supplier")
        supplier.delete()
        messages.success(request, "Supplier deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("suppliers:supplier_list")
    template = "suppliers/_delete.html" if is_htmx(request) else "suppliers/supplier_confirm_delete.html"
    return render(request, template, {"supplier": supplier})


@internal_only
def supplier_create_account(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method != "POST":
        return redirect("suppliers:supplier_list")
    if supplier.user_id:
        messages.error(request, f"{supplier.name} already has a portal account.")
        return redirect("suppliers:supplier_list")
    user, password = create_portal_account(supplier, "supplier", request.user)
    messages.success(
        request,
        f"Portal account created — username '{user.username}', temporary password '{password}'. "
        "Share these with the supplier; they must change the password after first login.",
    )
    log_activity(request.user, "update", "Supplier", supplier.pk, supplier.name, "Created portal account")
    return redirect("suppliers:supplier_list")


@admin_or_owner_required
def supplier_deactivate_account(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method != "POST":
        return redirect("suppliers:supplier_list")
    if not supplier.user_id:
        messages.error(request, f"{supplier.name} has no portal account.")
        return redirect("suppliers:supplier_list")
    supplier.is_active = False
    supplier.save()  # Supplier.save cascades user.is_active = False
    messages.success(request, f"Portal account for {supplier.name} deactivated.")
    log_activity(request.user, "update", "Supplier", supplier.pk, supplier.name, "Deactivated portal account")
    return redirect("suppliers:supplier_list")
