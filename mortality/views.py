from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import MortalityRecordForm
from .models import MortalityRecord
from flocks.models import FlockBatch
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def mortality_list(request):
    records = MortalityRecord.objects.all()
    return render(request, "mortality/mortality_list.html", {"records": records})


@login_required
def mortality_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = MortalityRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "MortalityRecord", record.pk, record.__str__(), "Created mortality record")
            messages.success(request, "Mortality record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("mortality:mortality_list")
    else:
        form = MortalityRecordForm()
    template = "mortality/_form.html" if is_htmx(request) else "mortality/mortality_form.html"
    return render(request, template, {"form": form, "flocks": flocks})


@login_required
def mortality_update(request, pk):
    record = get_object_or_404(MortalityRecord, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = MortalityRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "MortalityRecord", record.pk, record.__str__(), "Updated mortality record")
            messages.success(request, "Mortality record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("mortality:mortality_list")
    else:
        form = MortalityRecordForm(instance=record)
    template = "mortality/_form.html" if is_htmx(request) else "mortality/mortality_form.html"
    return render(request, template, {"form": form, "record": record, "flocks": flocks})


@login_required
def mortality_delete(request, pk):
    record = get_object_or_404(MortalityRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "MortalityRecord", record.pk, record.__str__(), "Deleted mortality record")
        record.delete()
        messages.success(request, "Mortality record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("mortality:mortality_list")
    template = "mortality/_delete.html" if is_htmx(request) else "mortality/mortality_confirm_delete.html"
    return render(request, template, {"record": record})
