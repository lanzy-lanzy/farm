from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import SupplierForm
from .models import Supplier
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all()
    return render(request, "suppliers/supplier_list.html", {"suppliers": suppliers})


@login_required
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


@login_required
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


@login_required
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
