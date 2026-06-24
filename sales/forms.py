from django import forms

from .models import SalesRecord


class SalesRecordForm(forms.ModelForm):
    class Meta:
        model = SalesRecord
        fields = [
            "product_type",
            "flock",
            "buyer",
            "product_name",
            "quantity",
            "unit_price",
            "date_sold",
            "payment_status",
            "amount_paid",
            "notes",
        ]
        widgets = {
            "product_type": forms.Select(attrs={"class": "form-input"}),
            "flock": forms.Select(attrs={"class": "form-input"}),
            "buyer": forms.Select(attrs={"class": "form-input"}),
            "product_name": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "date_sold": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "payment_status": forms.Select(attrs={"class": "form-input"}),
            "amount_paid": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }
