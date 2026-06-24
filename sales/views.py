from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import SalesRecordForm
from .models import SalesRecord
from flocks.models import FlockBatch
from buyers.models import Buyer
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def sales_list(request):
    records = SalesRecord.objects.all()
    return render(request, "sales/sales_list.html", {"records": records})


@login_required
def sales_detail(request, pk):
    record = get_object_or_404(SalesRecord, pk=pk)
    return render(request, "sales/sales_detail.html", {"record": record})


@login_required
def sales_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    buyers_list = Buyer.objects.filter(is_active=True)
    if request.method == "POST":
        form = SalesRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "SalesRecord", record.pk, record.__str__(), "Created sales record")
            messages.success(request, "Sales record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("sales:sales_list")
    else:
        form = SalesRecordForm()
    template = "sales/_form.html" if is_htmx(request) else "sales/sales_form.html"
    return render(request, template, {"form": form, "flocks": flocks, "buyers": buyers_list})


@login_required
def sales_update(request, pk):
    record = get_object_or_404(SalesRecord, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    buyers_list = Buyer.objects.filter(is_active=True)
    if request.method == "POST":
        form = SalesRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "SalesRecord", record.pk, record.__str__(), "Updated sales record")
            messages.success(request, "Sales record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("sales:sales_list")
    else:
        form = SalesRecordForm(instance=record)
    template = "sales/_form.html" if is_htmx(request) else "sales/sales_form.html"
    return render(request, template, {"form": form, "record": record, "flocks": flocks, "buyers": buyers_list})


@login_required
def sales_delete(request, pk):
    record = get_object_or_404(SalesRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "SalesRecord", record.pk, record.__str__(), "Deleted sales record")
        record.delete()
        messages.success(request, "Sales record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("sales:sales_list")
    template = "sales/_delete.html" if is_htmx(request) else "sales/sales_confirm_delete.html"
    return render(request, template, {"record": record})
