from django.contrib import admin

from .models import ExpenseRecord, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]


@admin.register(ExpenseRecord)
class ExpenseRecordAdmin(admin.ModelAdmin):
    list_display = ["category", "description", "amount", "expense_date", "payment_method"]
    list_filter = ["category", "payment_method"]
