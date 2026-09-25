from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import DeathRecordForm
from .models import DeathRecord
from flocks.models import FlockBatch
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def death_list(request):
    records = DeathRecord.objects.all()
    return render(request, "deaths/death_list.html", {"records": records})


@internal_only
def death_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = DeathRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "DeathRecord", record.pk, record.__str__(), "Created death record")
            messages.success(request, "Death record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("deaths:death_list")
    else:
        form = DeathRecordForm()
    template = "deaths/_form.html" if is_htmx(request) else "deaths/death_form.html"
    return render(request, template, {"form": form, "flocks": flocks})


@internal_only
def death_update(request, pk):
    record = get_object_or_404(DeathRecord, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = DeathRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "DeathRecord", record.pk, record.__str__(), "Updated death record")
            messages.success(request, "Death record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("deaths:death_list")
    else:
        form = DeathRecordForm(instance=record)
    template = "deaths/_form.html" if is_htmx(request) else "deaths/death_form.html"
    return render(request, template, {"form": form, "record": record, "flocks": flocks})


@internal_only
def death_delete(request, pk):
    record = get_object_or_404(DeathRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "DeathRecord", record.pk, record.__str__(), "Deleted death record")
        record.delete()
        messages.success(request, "Death record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("deaths:death_list")
    template = "deaths/_delete.html" if is_htmx(request) else "deaths/death_confirm_delete.html"
    return render(request, template, {"record": record})
