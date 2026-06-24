from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from .forms import ExpenseRecordForm, ExpenseCategoryForm
from .models import ExpenseRecord, ExpenseCategory
from notifications.utils import log_activity


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


@login_required
def expense_list(request):
    records = ExpenseRecord.objects.all()
    return render(request, "expenses/expense_list.html", {"records": records})


@login_required
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


@login_required
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


@login_required
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


@login_required
def expense_category_list(request):
    categories = ExpenseCategory.objects.all()
    return render(request, "expenses/category_list.html", {"categories": categories})


@login_required
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
