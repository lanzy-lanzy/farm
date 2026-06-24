from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import EggProductionForm
from .models import EggProduction
from flocks.models import FlockBatch
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def egg_list(request):
    records = EggProduction.objects.all()
    flock_filter = request.GET.get("flock", "")
    if flock_filter:
        records = records.filter(flock_id=flock_filter)
    return render(request, "eggs/egg_list.html", {"records": records, "flock_filter": flock_filter})


@login_required
def egg_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = EggProductionForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "EggProduction", record.pk, record.__str__(), "Created egg production record")
            messages.success(request, "Egg production record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("eggs:egg_list")
    else:
        form = EggProductionForm()
    template = "eggs/_form.html" if is_htmx(request) else "eggs/egg_form.html"
    return render(request, template, {"form": form, "flocks": flocks})


@login_required
def egg_update(request, pk):
    record = get_object_or_404(EggProduction, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    if request.method == "POST":
        form = EggProductionForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "EggProduction", record.pk, record.__str__(), "Updated egg production record")
            messages.success(request, "Egg production record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("eggs:egg_list")
    else:
        form = EggProductionForm(instance=record)
    template = "eggs/_form.html" if is_htmx(request) else "eggs/egg_form.html"
    return render(request, template, {"form": form, "record": record, "flocks": flocks})


@login_required
def egg_delete(request, pk):
    record = get_object_or_404(EggProduction, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "EggProduction", record.pk, record.__str__(), "Deleted egg production record")
        record.delete()
        messages.success(request, "Egg production record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("eggs:egg_list")
    template = "eggs/_delete.html" if is_htmx(request) else "eggs/egg_confirm_delete.html"
    return render(request, template, {"record": record})
