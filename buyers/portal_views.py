from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access import external_portal_required
from config.htmx import is_htmx, modal_closed
from notifications.utils import notify_team

from .forms import BuyerProfileForm, OrderRequestForm
from .models import OrderRequest


def _buyer(request):
    return request.user.buyer


@external_portal_required("buyer")
def buyer_home(request):
    buyer = _buyer(request)
    requests = buyer.order_requests.all()[:5]
    recent_sales = buyer.sales_records.all()[:5]
    open_requests = buyer.order_requests.filter(
        status__in=["submitted", "under_review", "quoted", "accepted"]
    ).count()
    awaiting_response = buyer.order_requests.filter(status="quoted")[:3]
    return render(
        request,
        "portal/buyer/home.html",
        {
            "buyer": buyer,
            "requests": requests,
            "recent_sales": recent_sales,
            "open_requests": open_requests,
            "awaiting_response": awaiting_response,
            "outstanding": buyer.outstanding_balance,
        },
    )


@external_portal_required("buyer")
def order_request_list(request):
    buyer = _buyer(request)
    requests = buyer.order_requests.all()
    return render(
        request, "portal/buyer/requests_list.html", {"buyer": buyer, "requests": requests}
    )


@external_portal_required("buyer")
def order_request_create(request):
    buyer = _buyer(request)
    if request.method == "POST":
        form = OrderRequestForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.buyer = buyer
            order.created_by = request.user
            order.save()
            notify_team(
                "order_request",
                f"New order request {order.request_number}",
                f"{buyer.name} requested {order.quantity} {order.product_name}.",
                link=f"/sales/requests/{order.pk}/",
                target=f"order_request:{order.pk}",
            )
            messages.success(request, f"Request {order.request_number} submitted.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:buyer_request_detail", pk=order.pk)
    else:
        form = OrderRequestForm()
    template = (
        "portal/buyer/_request_form.html"
        if is_htmx(request)
        else "portal/buyer/request_form.html"
    )
    return render(request, template, {"buyer": buyer, "form": form})


@external_portal_required("buyer")
def order_request_detail(request, pk):
    """Read view: dialog fragment for HTMX callers, standalone page for deep links."""
    order = get_object_or_404(OrderRequest, pk=pk, buyer=_buyer(request))
    if is_htmx(request):
        return render(request, "portal/buyer/_request_detail.html", {"order": order})
    return render(request, "portal/buyer/request_detail.html", {"order": order})


@external_portal_required("buyer")
def order_request_respond(request, pk):
    order = get_object_or_404(OrderRequest, pk=pk, buyer=_buyer(request))
    if request.method != "POST":
        return redirect("portal:buyer_request_detail", pk=order.pk)
    action = request.POST.get("action")
    if action == "accept" and order.can_accept():
        order.status = "accepted"
        order.save()
        notify_team(
            "order_request",
            f"Quote accepted for {order.request_number}",
            f"{order.buyer.name} accepted the quote. Ready to record the sale.",
            link=f"/sales/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        messages.success(request, "Quote accepted. The farm will now prepare your order.")
    elif action == "decline" and order.can_accept():
        order.status = "rejected"
        order.save()
        notify_team(
            "order_request",
            f"Quote declined for {order.request_number}",
            f"{order.buyer.name} declined the quote.",
            link=f"/sales/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        messages.success(request, "Quote declined.")
    else:
        messages.error(request, "This request can no longer be changed.")
    if is_htmx(request):
        return modal_closed()
    return redirect("portal:buyer_request_detail", pk=order.pk)


@external_portal_required("buyer")
def order_request_cancel(request, pk):
    order = get_object_or_404(OrderRequest, pk=pk, buyer=_buyer(request))
    if request.method == "POST":
        if order.is_cancellable:
            order.status = "cancelled"
            order.save()
            notify_team(
                "order_request",
                f"Request {order.request_number} cancelled",
                f"{order.buyer.name} cancelled the request.",
                link="/sales/requests/",
                target=f"order_request:{order.pk}",
            )
            messages.success(request, "Request cancelled.")
        else:
            messages.error(request, "This request can no longer be cancelled.")
        if is_htmx(request):
            return modal_closed()
        return redirect("portal:buyer_request_detail", pk=order.pk)
    if not is_htmx(request):
        return redirect("portal:buyer_request_detail", pk=order.pk)
    return render(request, "portal/buyer/_request_cancel.html", {"order": order})


@external_portal_required("buyer")
def buyer_profile(request):
    return render(request, "portal/buyer/profile.html", {"buyer": _buyer(request)})


@external_portal_required("buyer")
def buyer_profile_update(request):
    buyer = _buyer(request)
    if request.method == "POST":
        form = BuyerProfileForm(request.POST, instance=buyer)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            if is_htmx(request):
                return modal_closed()
            return redirect("portal:buyer_profile")
    else:
        if not is_htmx(request):
            return redirect("portal:buyer_profile")
        form = BuyerProfileForm(instance=buyer)
    return render(
        request, "portal/buyer/_profile_form.html", {"buyer": buyer, "form": form}
    )
