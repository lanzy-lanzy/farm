from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import FeedingRecordForm
from .models import FeedingRecord
from flocks.models import FlockBatch
from inventory.models import InventoryItem
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def feeding_list(request):
    records = FeedingRecord.objects.all()
    return render(request, "feeding/feeding_list.html", {"records": records})


@internal_only
def feeding_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    feed_items = InventoryItem.objects.filter(category__name__iexact="Feeds", is_active=True)
    if request.method == "POST":
        form = FeedingRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "FeedingRecord", record.pk, record.__str__(), "Created feeding record")
            messages.success(request, "Feeding record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("feeding:feeding_list")
    else:
        form = FeedingRecordForm()
    template = "feeding/_form.html" if is_htmx(request) else "feeding/feeding_form.html"
    return render(request, template, {"form": form, "flocks": flocks, "feed_items": feed_items})


@internal_only
def feeding_update(request, pk):
    record = get_object_or_404(FeedingRecord, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    feed_items = InventoryItem.objects.filter(category__name__iexact="Feeds", is_active=True)
    if request.method == "POST":
        form = FeedingRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "FeedingRecord", record.pk, record.__str__(), "Updated feeding record")
            messages.success(request, "Feeding record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("feeding:feeding_list")
    else:
        form = FeedingRecordForm(instance=record)
    template = "feeding/_form.html" if is_htmx(request) else "feeding/feeding_form.html"
    return render(request, template, {"form": form, "record": record, "flocks": flocks, "feed_items": feed_items})


@internal_only
def feeding_delete(request, pk):
    record = get_object_or_404(FeedingRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "FeedingRecord", record.pk, record.__str__(), "Deleted feeding record")
        record.delete()
        messages.success(request, "Feeding record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("feeding:feeding_list")
    template = "feeding/_delete.html" if is_htmx(request) else "feeding/feeding_confirm_delete.html"
    return render(request, template, {"record": record})


@internal_only
def feeding_history(request, flock_id):
    records = FeedingRecord.objects.filter(flock_id=flock_id)
    return render(request, "feeding/feeding_history.html", {"records": records})
