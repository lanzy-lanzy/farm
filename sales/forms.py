from django import forms

from buyers.models import Buyer, OrderRequest
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


class OrderRequestQuoteForm(forms.ModelForm):
    class Meta:
        model = OrderRequest
        fields = ["quoted_unit_price", "staff_note"]
        widgets = {
            "quoted_unit_price": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": 0}
            ),
            "staff_note": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quoted_unit_price"].required = False
        self.fields["staff_note"].required = False


class OrderRequestOnBehalfForm(forms.ModelForm):
    """Staff-created request for phone/walk-in buyers; enters the funnel at accepted."""

    class Meta:
        model = OrderRequest
        fields = [
            "buyer", "product_type", "product_name", "quantity",
            "requested_unit_price", "requested_date", "staff_note",
        ]
        widgets = {
            "buyer": forms.Select(attrs={"class": "form-input"}),
            "product_type": forms.Select(attrs={"class": "form-input"}),
            "product_name": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": "0.01"}),
            "requested_unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "requested_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "staff_note": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["buyer"].queryset = Buyer.objects.filter(is_active=True)
        self.fields["requested_unit_price"].required = False
        self.fields["staff_note"].required = False
