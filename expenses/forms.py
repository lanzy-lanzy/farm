from django import forms

from .models import ExpenseRecord, ExpenseCategory


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }


class ExpenseRecordForm(forms.ModelForm):
    class Meta:
        model = ExpenseRecord
        fields = [
            "category",
            "description",
            "amount",
            "expense_date",
            "payment_method",
            "receipt",
            "notes",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-input"}),
            "description": forms.TextInput(attrs={"class": "form-input"}),
            "amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "expense_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "payment_method": forms.Select(attrs={"class": "form-input"}),
            "receipt": forms.FileInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }
