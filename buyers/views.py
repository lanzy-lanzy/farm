from django.contrib import messages
from accounts.access import internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils import timezone
from django.http import HttpResponse

from .forms import BuyerForm
from .models import Buyer
from accounts.access import admin_or_owner_required, create_portal_account
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def buyer_list(request):
    buyers = Buyer.objects.all()
    return render(request, "buyers/buyer_list.html", {"buyers": buyers})


@internal_only
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


@internal_only
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


@internal_only
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


@internal_only
def buyer_create_account(request, pk):
    buyer = get_object_or_404(Buyer, pk=pk)
    if request.method != "POST":
        return redirect("buyers:buyer_list")
    if buyer.user_id:
        messages.error(request, f"{buyer.name} already has a portal account.")
        return redirect("buyers:buyer_list")
    user, password = create_portal_account(buyer, "buyer", request.user)
    messages.success(
        request,
        f"Portal account created — username '{user.username}', temporary password '{password}'. "
        "Share these with the buyer; they must change the password after first login.",
    )
    log_activity(request.user, "update", "Buyer", buyer.pk, buyer.name, "Created portal account")
    return redirect("buyers:buyer_list")


@admin_or_owner_required
def buyer_deactivate_account(request, pk):
    buyer = get_object_or_404(Buyer, pk=pk)
    if request.method != "POST":
        return redirect("buyers:buyer_list")
    if not buyer.user_id:
        messages.error(request, f"{buyer.name} has no portal account.")
        return redirect("buyers:buyer_list")
    buyer.is_active = False
    buyer.save()  # Buyer.save cascades user.is_active = False
    messages.success(request, f"Portal account for {buyer.name} deactivated.")
    log_activity(request.user, "update", "Buyer", buyer.pk, buyer.name, "Deactivated portal account")
    return redirect("buyers:buyer_list")
