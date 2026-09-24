from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import MedicineRecordForm
from .models import MedicineRecord
from flocks.models import FlockBatch
from notifications.utils import notify_vaccination_due, log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def medicine_list(request):
    records = MedicineRecord.objects.all()
    return render(request, "medicine/medicine_list.html", {"records": records})


@internal_only
def medicine_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = MedicineRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "MedicineRecord", record.pk, record.medicine_name, "Created medicine record")
            if record.medicine_type == "vaccine" and record.next_schedule:
                notify_vaccination_due(record, request)
            messages.success(request, "Medicine record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("medicine:medicine_list")
    else:
        form = MedicineRecordForm()
    template = "medicine/_form.html" if is_htmx(request) else "medicine/medicine_form.html"
    return render(request, template, {"form": form, "flocks": flocks})


@internal_only
def medicine_update(request, pk):
    record = get_object_or_404(MedicineRecord, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = MedicineRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "MedicineRecord", record.pk, record.medicine_name, "Updated medicine record")
            messages.success(request, "Medicine record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("medicine:medicine_list")
    else:
        form = MedicineRecordForm(instance=record)
    template = "medicine/_form.html" if is_htmx(request) else "medicine/medicine_form.html"
    return render(request, template, {"form": form, "record": record, "flocks": flocks})


@internal_only
def medicine_delete(request, pk):
    record = get_object_or_404(MedicineRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "MedicineRecord", record.pk, record.medicine_name, "Deleted medicine record")
        record.delete()
        messages.success(request, "Medicine record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("medicine:medicine_list")
    template = "medicine/_delete.html" if is_htmx(request) else "medicine/medicine_confirm_delete.html"
    return render(request, template, {"record": record})


@internal_only
def vaccination_schedule(request):
    from django.utils import timezone
    upcoming = MedicineRecord.objects.filter(
        medicine_type="vaccine",
        next_schedule__gte=timezone.now().date(),
    ).order_by("next_schedule")
    return render(request, "medicine/vaccination_schedule.html", {"upcoming": upcoming})
