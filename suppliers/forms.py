from django import forms

from .models import DeliveryNotice, Supplier, SupplyItem


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "supplies",
            "notes",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "supplies": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }


class SupplyItemForm(forms.ModelForm):
    class Meta:
        model = SupplyItem
        fields = ["name", "category", "unit_price", "unit", "availability"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "category": forms.TextInput(attrs={"class": "form-input"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": "0.01"}),
            "unit": forms.Select(attrs={"class": "form-input"}),
            "availability": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from inventory.models import Unit

        self.fields["unit"].queryset = Unit.objects.all()
        self.fields["unit"].required = False


class DeliveryNoticeForm(forms.ModelForm):
    class Meta:
        model = DeliveryNotice
        fields = ["supply_item", "description", "quantity", "expected_date"]
        widgets = {
            "supply_item": forms.Select(attrs={"class": "form-input"}),
            "description": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": "0.01"}),
            "expected_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supply_item"].queryset = (
            SupplyItem.objects.filter(supplier=supplier, is_active=True) if supplier else SupplyItem.objects.none()
        )
        self.fields["supply_item"].required = False


class FarmDeliveryOrderForm(forms.ModelForm):
    """Staff places an order with a supplier (origin=farm)."""

    class Meta:
        model = DeliveryNotice
        fields = ["supplier", "supply_item", "description", "quantity", "expected_date"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-input"}),
            "supply_item": forms.Select(attrs={"class": "form-input"}),
            "description": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": "0.01"}),
            "expected_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(
            is_active=True, verification_status="approved"
        )
        self.fields["supply_item"].queryset = SupplyItem.objects.filter(is_active=True)
        self.fields["supply_item"].required = False

    def clean(self):
        cleaned = super().clean()
        supplier = cleaned.get("supplier")
        item = cleaned.get("supply_item")
        if item and supplier and item.supplier_id != supplier.pk:
            self.add_error("supply_item", "This item is not in the selected supplier's catalog.")
        if not item and not cleaned.get("description"):
            self.add_error("description", "Describe what you are ordering.")
        return cleaned


class FarmOrderResponseForm(forms.ModelForm):
    """Supplier may only adjust the date and add a note on a farm-ordered delivery."""

    class Meta:
        model = DeliveryNotice
        fields = ["expected_date", "supplier_note"]
        widgets = {
            "expected_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "supplier_note": forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional note for the farm"}),
        }


class SupplierProfileForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "supplies"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "supplies": forms.TextInput(attrs={"class": "form-input"}),
        }
