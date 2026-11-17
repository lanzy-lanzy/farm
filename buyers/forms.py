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
    product = forms.ModelChoiceField(queryset=None, widget=forms.Select(attrs={"class": "form-input"}))

    class Meta:
        model = OrderRequest
        fields = ["product", "quantity"]
        widgets = {"quantity": forms.NumberInput(attrs={"class": "form-input", "min": "0.01", "step": "0.01"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from sales.models import Product
        self.fields["product"].queryset = Product.objects.filter(is_active=True)
        self.fields["product"].label_from_instance = lambda p: f"{p.name} — {p.unit_price} / {p.unit_label}"
        self.fields["product"].help_text = "Product name, unit and fixed price come from the farm catalog."

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity <= 0:
            raise forms.ValidationError("Enter a positive quantity.")
        return quantity

    def save(self, commit=True):
        product = self.cleaned_data["product"]
        self.instance.product_type = product.product_type
        self.instance.product_name = product.name
        self.instance.requested_unit_price = product.unit_price
        return super().save(commit=commit)


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
