from decimal import Decimal

from django.contrib import messages
from accounts.access import admin_or_owner_required, internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import HttpResponse

from .forms import OrderRequestOnBehalfForm, OrderRequestQuoteForm, SalesRecordForm
from .models import SalesRecord
from buyers.models import OrderRequest
from flocks.models import FlockBatch
from buyers.models import Buyer
from notifications.utils import log_activity, notify_user


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def is_elevated(user):
    """Owner/admin: may correct financials, override quotes and credit limits."""
    return user.is_admin_user() or user.is_owner()


def credit_block_reason(buyer, new_unpaid):
    """Return a human-readable reason the sale breaches the buyer's credit limit, or None."""
    if buyer is None or buyer.credit_limit is None or new_unpaid is None or new_unpaid <= 0:
        return None
    projected = buyer.outstanding_balance + new_unpaid
    if projected > buyer.credit_limit:
        return (
            f"{buyer.name} would owe ₱{projected:,.2f} against a credit limit of "
            f"₱{buyer.credit_limit:,.2f}."
        )
    return None


@internal_only
def sales_list(request):
    records = SalesRecord.objects.all()
    return render(request, "sales/sales_list.html", {"records": records})


@internal_only
def sales_detail(request, pk):
    record = get_object_or_404(SalesRecord, pk=pk)
    return render(request, "sales/sales_detail.html", {"record": record})


@internal_only
def sales_create(request):
    flocks = FlockBatch.objects.filter(status="active")
    buyers_list = Buyer.objects.filter(is_active=True)
    linked_order = None
    order_id = request.POST.get("order_request") or request.GET.get("order_request")
    if order_id:
        linked_order = OrderRequest.objects.filter(pk=order_id).first()
    if request.method == "POST":
        form = SalesRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            # total_amount is only computed inside save(), so derive it for the gate.
            new_unpaid = record.quantity * record.unit_price - record.amount_paid
            reason = (
                credit_block_reason(record.buyer, new_unpaid)
                if record.payment_status != "paid"
                else None
            )
            if reason and not is_elevated(request.user):
                form.add_error(
                    None,
                    f"Credit limit exceeded — {reason} Ask an owner or administrator to record this sale.",
                )
            else:
                record.recorded_by = request.user
                record.save()
                if reason and is_elevated(request.user):
                    log_activity(
                        request.user, "update", "SalesRecord", record.pk,
                        record.__str__(), f"Credit limit override: {reason}",
                    )
                if linked_order and linked_order.can_convert():
                    linked_order.sales_record = record
                    linked_order.status = "converted"
                    linked_order.save()
                    notify_user(
                        linked_order.buyer.user,
                        "order_request",
                        f"Order {linked_order.request_number} recorded as sold",
                        f"Sale of {record.quantity} {record.product_name} for {record.total_amount} has been recorded.",
                        link=f"/portal/buyer/requests/{linked_order.pk}/",
                    )
                log_activity(request.user, "create", "SalesRecord", record.pk, record.__str__(), "Created sales record")
                messages.success(request, "Sales record created successfully.")
                if is_htmx(request):
                    return HttpResponse(
                        '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                    )
                return redirect("sales:sales_list")
    else:
        initial = {}
        if linked_order:
            initial = {
                "product_type": linked_order.product_type,
                "product_name": linked_order.product_name,
                "quantity": linked_order.quantity,
                "unit_price": linked_order.effective_unit_price,
                "buyer": linked_order.buyer,
                "date_sold": timezone.localdate(),
                "notes": f"From order request {linked_order.request_number}",
            }
        form = SalesRecordForm(initial=initial)
    template = "sales/_form.html" if is_htmx(request) else "sales/sales_form.html"
    return render(
        request,
        template,
        {
            "form": form,
            "flocks": flocks,
            "buyers": buyers_list,
            "order_request_id": linked_order.pk if linked_order else "",
        },
    )


@admin_or_owner_required
def sales_update(request, pk):
    record = get_object_or_404(SalesRecord, pk=pk)
    flocks = FlockBatch.objects.filter(status="active")
    buyers_list = Buyer.objects.filter(is_active=True)
    if request.method == "POST":
        old_total = record.total_amount
        form = SalesRecordForm(request.POST, instance=record)
        if form.is_valid():
            updated = form.save(commit=False)
            new_unpaid = updated.quantity * updated.unit_price - updated.amount_paid
            reason = (
                credit_block_reason(updated.buyer, new_unpaid)
                if updated.payment_status != "paid"
                else None
            )
            if reason:
                form.add_error(None, f"Credit limit exceeded — {reason}")
            else:
                updated.save()
                diff = (
                    f" (₱{old_total:,.2f} → ₱{updated.total_amount:,.2f})"
                    if old_total != updated.total_amount
                    else ""
                )
                log_activity(request.user, "update", "SalesRecord", record.pk, record.__str__(), f"Corrected sales record{diff}")
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


@admin_or_owner_required
def sales_delete(request, pk):
    record = get_object_or_404(SalesRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "SalesRecord", record.pk, record.__str__(), f"Deleted sales record (total ₱{record.total_amount:,.2f})")
        record.delete()
        messages.success(request, "Sales record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("sales:sales_list")
    template = "sales/_delete.html" if is_htmx(request) else "sales/sales_confirm_delete.html"
    return render(request, template, {"record": record})


@internal_only
def order_request_queue(request):
    orders = OrderRequest.objects.select_related("buyer")
    status_filter = request.GET.get("status", "")
    if status_filter:
        orders = orders.filter(status=status_filter)
    open_count = OrderRequest.objects.filter(
        status__in=["submitted", "under_review", "quoted", "accepted"]
    ).count()
    return render(
        request,
        "sales/order_request_queue.html",
        {
            "orders": orders,
            "open_count": open_count,
            "status_filter": status_filter,
            "statuses": OrderRequest.STATUS_CHOICES,
        },
    )


@internal_only
def order_request_create_internal(request):
    """Staff records a phone/walk-in order on behalf of a buyer — enters the funnel at accepted."""
    if request.method == "POST":
        form = OrderRequestOnBehalfForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.source = "staff"
            order.status = "accepted"
            order.created_by = request.user
            order.save()
            log_activity(request.user, "create", "OrderRequest", order.pk, order.request_number, "Created on behalf of buyer")
            messages.success(request, f"Order {order.request_number} recorded — convert it to a sale when delivered.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("sales:order_request_queue")
    else:
        form = OrderRequestOnBehalfForm()
    template = "sales/_onbehalf_form.html" if is_htmx(request) else "sales/order_request_onbehalf.html"
    return render(request, template, {"form": form})


@internal_only
def order_request_review(request, pk):
    order = get_object_or_404(OrderRequest.objects.select_related("buyer"), pk=pk)
    if request.method == "GET" and is_htmx(request) and request.GET.get("form") in ("quote", "requote", "reject"):
        modal_form = request.GET.get("form")
        allowed = {
            "quote": order.can_quote(),
            "requote": order.can_requote(),
            "reject": order.status in ("submitted", "under_review", "quoted"),
        }[modal_form]
        if not allowed:
            return redirect("sales:order_request_review", pk=order.pk)
        return render(
            request,
            "sales/_review_modal.html",
            {"order": order, "modal_form": modal_form, "form": OrderRequestQuoteForm(instance=order)},
        )
    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("quote", "requote") and (
            (action == "quote" and order.can_quote()) or (action == "requote" and order.can_requote())
        ):
            form = OrderRequestQuoteForm(request.POST, instance=order)
            if form.is_valid():
                order = form.save(commit=False)
                order.status = "quoted"
                order.save()
                notify_user(
                    order.buyer.user,
                    "order_request",
                    f"Quote ready for {order.request_number}",
                    f"The farm quoted {order.quoted_unit_price} per unit. Review and accept or decline in your portal.",
                    link=f"/portal/buyer/requests/{order.pk}/",
                )
                messages.success(request, f"Quote sent to {order.buyer.name}.")
                if is_htmx(request):
                    return HttpResponse(
                        '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                    )
                return redirect("sales:order_request_queue")
            if is_htmx(request):
                return render(
                    request,
                    "sales/_review_modal.html",
                    {"order": order, "modal_form": action, "form": form},
                )
        elif action == "start_review" and order.can_quote():
            order.status = "under_review"
            order.save()
            messages.success(request, "Request marked as under review.")
            return redirect("sales:order_request_review", pk=order.pk)
        elif action == "reject":
            order.status = "rejected"
            order.staff_note = request.POST.get("staff_note", "").strip() or order.staff_note
            order.save()
            notify_user(
                order.buyer.user,
                "order_request",
                f"Request {order.request_number} declined",
                order.staff_note or "The farm could not fulfil this request.",
                link=f"/portal/buyer/requests/{order.pk}/",
            )
            messages.success(request, "Request rejected.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("sales:order_request_queue")
        else:
            form = OrderRequestQuoteForm(instance=order)
    else:
        form = OrderRequestQuoteForm(instance=order)
    return render(
        request, "sales/order_request_review.html", {"order": order, "form": form}
    )


@internal_only
def order_request_convert(request, pk):
    """Explicit conversion of an accepted request into a SalesRecord, with credit + price gates."""
    order = get_object_or_404(OrderRequest.objects.select_related("buyer"), pk=pk)
    if not order.can_convert():
        messages.error(request, "This request is not ready to be converted.")
        return redirect("sales:order_request_review", pk=order.pk)

    flocks = FlockBatch.objects.filter(status="active")
    buyers_list = Buyer.objects.filter(is_active=True)
    elevated = is_elevated(request.user)

    if request.method == "POST":
        form = SalesRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            if (
                not elevated
                and order.effective_unit_price is not None
                and record.unit_price != order.effective_unit_price
            ):
                form.add_error(
                    "unit_price",
                    "Only an owner or administrator may change the accepted quote price.",
                )
            else:
                new_unpaid = record.quantity * record.unit_price - record.amount_paid
                reason = (
                    credit_block_reason(record.buyer, new_unpaid)
                    if record.payment_status != "paid"
                    else None
                )
                if reason and not elevated:
                    form.add_error(
                        None,
                        f"Credit limit exceeded — {reason} Record as paid, take a partial payment, or ask an owner/administrator to override.",
                    )
                else:
                    record.recorded_by = request.user
                    record.save()
                    order.sales_record = record
                    order.status = "converted"
                    order.save()
                    if reason and elevated:
                        log_activity(
                            request.user, "update", "OrderRequest", order.pk,
                            order.request_number, f"Credit limit override at conversion: {reason}",
                        )
                    log_activity(request.user, "create", "SalesRecord", record.pk, record.__str__(), f"Converted from {order.request_number}")
                    notify_user(
                        order.buyer.user,
                        "order_request",
                        f"Order {order.request_number} recorded as sold",
                        f"Sale of {record.quantity} {record.product_name} for {record.total_amount} has been recorded.",
                        link=f"/portal/buyer/requests/{order.pk}/",
                    )
                    messages.success(request, f"{order.request_number} converted to a sale.")
                    return redirect("sales:order_request_queue")
    else:
        form = SalesRecordForm(
            initial={
                "product_type": order.product_type,
                "product_name": order.product_name,
                "quantity": order.quantity,
                "unit_price": order.effective_unit_price or Decimal("0.00"),
                "buyer": order.buyer,
                "date_sold": timezone.localdate(),
                "notes": f"From order request {order.request_number}",
            }
        )
    return render(
        request,
        "sales/order_request_convert.html",
        {
            "form": form,
            "order": order,
            "flocks": flocks,
            "buyers": buyers_list,
            "elevated": elevated,
            "credit_limit": order.buyer.credit_limit,
            "outstanding": order.buyer.outstanding_balance,
        },
    )
