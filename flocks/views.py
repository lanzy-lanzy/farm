from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.http import HttpResponse

from .forms import FlockBatchForm
from .models import FlockBatch
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def flock_list(request):
    flocks = FlockBatch.objects.all()
    status_filter = request.GET.get("status", "")
    if status_filter:
        flocks = flocks.filter(status=status_filter)
    return render(request, "flocks/flock_list.html", {"flocks": flocks, "status_filter": status_filter})


@internal_only
def flock_detail(request, pk):
    flock = get_object_or_404(FlockBatch, pk=pk)
    return render(request, "flocks/flock_detail.html", {"flock": flock})


@internal_only
def flock_create(request):
    if request.method == "POST":
        form = FlockBatchForm(request.POST)
        if form.is_valid():
            flock = form.save(commit=False)
            flock.created_by = request.user
            flock.save()
            log_activity(request.user, "create", "FlockBatch", flock.pk, flock.batch_number, "Created flock batch")
            messages.success(request, "Flock batch created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("flocks:flock_list")
    else:
        form = FlockBatchForm()
    template = "flocks/_form.html" if is_htmx(request) else "flocks/flock_form.html"
    return render(request, template, {"form": form})


@internal_only
def flock_update(request, pk):
    flock = get_object_or_404(FlockBatch, pk=pk)
    if request.method == "POST":
        form = FlockBatchForm(request.POST, instance=flock)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "FlockBatch", flock.pk, flock.batch_number, "Updated flock batch")
            messages.success(request, "Flock batch updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("flocks:flock_list")
    else:
        form = FlockBatchForm(instance=flock)
    template = "flocks/_form.html" if is_htmx(request) else "flocks/flock_form.html"
    return render(request, template, {"form": form, "flock": flock})


@internal_only
def flock_delete(request, pk):
    flock = get_object_or_404(FlockBatch, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "FlockBatch", flock.pk, flock.batch_number, "Deleted flock batch")
        flock.delete()
        messages.success(request, "Flock batch deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("flocks:flock_list")
    template = "flocks/_delete.html" if is_htmx(request) else "flocks/flock_confirm_delete.html"
    return render(request, template, {"flock": flock})
