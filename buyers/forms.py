from django import forms

from .models import Buyer, OrderRequest


class BuyerForm(forms.ModelForm):
    class Meta:
        model = Buyer
        fields = [
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "buyer_type",
            "notes",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "buyer_type": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }


class OrderRequestForm(forms.ModelForm):
    class Meta:
        model = OrderRequest
        fields = [
            "product_type",
            "product_name",
            "quantity",
            "requested_unit_price",
            "requested_date",
        ]
        widgets = {
            "product_type": forms.Select(attrs={"class": "form-input"}),
            "product_name": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": "0.01"}),
            "requested_unit_price": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "step": "0.01"}
            ),
            "requested_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }


class BuyerProfileForm(forms.ModelForm):
    class Meta:
        model = Buyer
        fields = [
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }
