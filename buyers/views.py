from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import BuyerForm
from .models import Buyer
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def buyer_list(request):
    buyers = Buyer.objects.all()
    return render(request, "buyers/buyer_list.html", {"buyers": buyers})


@login_required
def buyer_create(request):
    if request.method == "POST":
        form = BuyerForm(request.POST)
        if form.is_valid():
            buyer = form.save(commit=False)
            buyer.created_by = request.user
            buyer.save()
            log_activity(request.user, "create", "Buyer", buyer.pk, buyer.__str__(), "Created buyer")
            messages.success(request, "Buyer created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("buyers:buyer_list")
    else:
        form = BuyerForm()
    template = "buyers/_form.html" if is_htmx(request) else "buyers/buyer_form.html"
    return render(request, template, {"form": form})


@login_required
def buyer_update(request, pk):
    buyer = get_object_or_404(Buyer, pk=pk)
    if request.method == "POST":
        form = BuyerForm(request.POST, instance=buyer)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "Buyer", buyer.pk, buyer.__str__(), "Updated buyer")
            messages.success(request, "Buyer updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("buyers:buyer_list")
    else:
        form = BuyerForm(instance=buyer)
    template = "buyers/_form.html" if is_htmx(request) else "buyers/buyer_form.html"
    return render(request, template, {"form": form, "buyer": buyer})


@login_required
def buyer_delete(request, pk):
    buyer = get_object_or_404(Buyer, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "Buyer", buyer.pk, buyer.__str__(), "Deleted buyer")
        buyer.delete()
        messages.success(request, "Buyer deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("buyers:buyer_list")
    template = "buyers/_delete.html" if is_htmx(request) else "buyers/buyer_confirm_delete.html"
    return render(request, template, {"buyer": buyer})
