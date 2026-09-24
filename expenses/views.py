from decimal import Decimal

from django.contrib import messages
from accounts.access import admin_or_owner_required, internal_only
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import ExpenseRecordForm, ExpenseCategoryForm
from .models import ExpenseRecord, ExpenseCategory
from notifications.utils import log_activity, notify_user


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@internal_only
def expense_list(request):
    records = ExpenseRecord.objects.all()
    return render(request, "expenses/expense_list.html", {"records": records})


@internal_only
def expense_create(request):
    categories = ExpenseCategory.objects.all()
    if request.method == "POST":
        form = ExpenseRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            log_activity(request.user, "create", "ExpenseRecord", record.pk, record.__str__(), "Created expense record")
            messages.success(request, "Expense record created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("expenses:expense_list")
    else:
        form = ExpenseRecordForm()
    template = "expenses/_form.html" if is_htmx(request) else "expenses/expense_form.html"
    return render(request, template, {"form": form, "categories": categories})


@admin_or_owner_required
def expense_update(request, pk):
    record = get_object_or_404(ExpenseRecord, pk=pk)
    categories = ExpenseCategory.objects.all()
    if request.method == "POST":
        form = ExpenseRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            log_activity(request.user, "update", "ExpenseRecord", record.pk, record.__str__(), "Updated expense record")
            messages.success(request, "Expense record updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("expenses:expense_list")
    else:
        form = ExpenseRecordForm(instance=record)
    template = "expenses/_form.html" if is_htmx(request) else "expenses/expense_form.html"
    return render(request, template, {"form": form, "record": record, "categories": categories})


@admin_or_owner_required
def expense_delete(request, pk):
    record = get_object_or_404(ExpenseRecord, pk=pk)
    if request.method == "POST":
        log_activity(request.user, "delete", "ExpenseRecord", record.pk, record.__str__(), "Deleted expense record")
        record.delete()
        messages.success(request, "Expense record deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
            )
        return redirect("expenses:expense_list")
    template = "expenses/_delete.html" if is_htmx(request) else "expenses/expense_confirm_delete.html"
    return render(request, template, {"record": record})


@internal_only
def expense_category_list(request):
    categories = ExpenseCategory.objects.all()
    return render(request, "expenses/category_list.html", {"categories": categories})


@internal_only
def expense_category_create(request):
    if request.method == "POST":
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense category created successfully.")
            return redirect("expenses:expense_category_list")
    else:
        form = ExpenseCategoryForm()
    return render(request, "expenses/category_form.html", {"form": form})


@internal_only
def delivery_notice_queue(request):
    from suppliers.models import DeliveryNotice

    notices = DeliveryNotice.objects.select_related("supplier", "supply_item")
    status_filter = request.GET.get("status", "")
    if status_filter:
        notices = notices.filter(status=status_filter)
    open_count = DeliveryNotice.objects.filter(status="announced").count()
    return render(
        request,
        "expenses/delivery_notice_queue.html",
        {
            "notices": notices,
            "open_count": open_count,
            "status_filter": status_filter,
            "statuses": DeliveryNotice.STATUS_CHOICES,
        },
    )


@internal_only
def delivery_notice_create(request):
    """Farm-initiated purchase order (PO-lite): staff order from a supplier's catalog."""
    from suppliers.forms import FarmDeliveryOrderForm
    from suppliers.models import DeliveryNotice

    if request.method == "POST":
        form = FarmDeliveryOrderForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.origin = "farm"
            notice.status = "announced"
            notice.created_by = request.user
            notice.save()
            notify_user(
                notice.supplier.user,
                "delivery_notice",
                f"The farm ordered: {notice.description}",
                f"{notice.quantity} {notice.description} requested for {notice.expected_date}. Confirm or adjust the date in your portal.",
                link="/portal/supplier/deliveries/",
            )
            log_activity(request.user, "create", "DeliveryNotice", notice.pk, notice.__str__(), "Farm ordered from supplier")
            messages.success(request, f"Order sent to {notice.supplier.name}.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("expenses:delivery_notice_queue")
    else:
        form = FarmDeliveryOrderForm()
    template = "expenses/_farm_order_form.html" if is_htmx(request) else "expenses/delivery_notice_form.html"
    return render(request, template, {"form": form})


@internal_only
def delivery_notice_review(request, pk):
    from suppliers.models import DeliveryNotice

    notice = get_object_or_404(DeliveryNotice.objects.select_related("supplier", "supply_item"), pk=pk)
    categories = ExpenseCategory.objects.all()

    def receive_initial():
        amount = None
        if notice.supply_item and notice.supply_item.unit_price is not None:
            amount = (notice.supply_item.unit_price * notice.quantity).quantize(Decimal("0.01"))
        return {
            "description": f"{notice.quantity} {notice.description} from {notice.supplier.name}",
            "amount": amount,
            "expense_date": notice.expected_date,
        }

    if request.method == "GET" and is_htmx(request) and request.GET.get("form") in ("receive", "reject", "view"):
        modal_form = request.GET.get("form")
        if modal_form == "view":
            return render(request, "expenses/_delivery_detail_modal.html", {"notice": notice})
        if notice.status != "announced":
            return redirect("expenses:delivery_notice_review", pk=notice.pk)
        return render(
            request,
            "expenses/_review_modal.html",
            {
                "notice": notice,
                "modal_form": modal_form,
                "form": ExpenseRecordForm(initial=receive_initial()) if modal_form == "receive" else None,
            },
        )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reject":
            notice.status = "rejected"
            notice.save()
            notify_user(
                notice.supplier.user,
                "delivery_notice",
                f"Delivery rejected: {notice.description}",
                request.POST.get("note", "").strip() or "The farm could not accept this delivery.",
                link="/portal/supplier/deliveries/",
            )
            messages.success(request, "Delivery notice rejected.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("expenses:delivery_notice_queue")
        form = ExpenseRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.supplier = notice.supplier
            record.save()
            notice.status = "received"
            notice.expense_record = record
            notice.received_by = request.user
            notice.save()
            log_activity(request.user, "create", "ExpenseRecord", record.pk, record.__str__(), f"Received delivery from {notice.supplier.name}")
            notify_user(
                notice.supplier.user,
                "delivery_notice",
                f"Delivery received: {notice.description}",
                f"The farm booked {record.description} for {record.amount}.",
                link="/portal/supplier/history/",
            )
            messages.success(request, "Delivery received and expense recorded.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>document.getElementById("modal-overlay").remove();window.location.reload()</script>'
                )
            return redirect("expenses:delivery_notice_queue")
        if is_htmx(request):
            return render(
                request,
                "expenses/_review_modal.html",
                {"notice": notice, "modal_form": "receive", "form": form},
            )
    else:
        form = ExpenseRecordForm(initial=receive_initial())
    return render(
        request,
        "expenses/delivery_notice_review.html",
        {"notice": notice, "form": form, "categories": categories},
    )
