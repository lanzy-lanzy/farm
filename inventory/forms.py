from django import forms
from django.core.exceptions import ValidationError

from .models import InventoryItem, InventoryCategory, Unit, InventoryTransaction


class InventoryCategoryForm(forms.ModelForm):
    class Meta:
        model = InventoryCategory
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["name", "abbreviation"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "abbreviation": forms.TextInput(attrs={"class": "form-input"}),
        }


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "category",
            "name",
            "description",
            "quantity",
            "unit",
            "supplier",
            "cost_per_unit",
            "date_purchased",
            "expiration_date",
            "reorder_level",
            "sales_product_type",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-input"}),
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "unit": forms.Select(attrs={"class": "form-input"}),
            "supplier": forms.Select(attrs={"class": "form-input"}),
            "cost_per_unit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "date_purchased": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "reorder_level": forms.NumberInput(attrs={"class": "form-input"}),
            "sales_product_type": forms.Select(attrs={"class": "form-input"}),
        }


class InventoryTransactionForm(forms.ModelForm):
    class Meta:
        model = InventoryTransaction
        fields = ["item", "transaction_type", "quantity", "reference", "notes"]
        widgets = {
            "item": forms.Select(attrs={"class": "form-input"}),
            "transaction_type": forms.Select(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "reference": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }


class StockBookingForm(forms.Form):
    """Receive-step decision: where the delivered quantity lands in permanent stock.

    Left empty for a pure ad-hoc purchase with no stock tracking; the catalog
    mapping (when the notice has one) still applies, so this form only overrides.
    """

    inventory_item = forms.ModelChoiceField(
        label="Book into stock", queryset=InventoryItem.objects.none(),
        required=False, empty_label="-- Keep current mapping / no booking --",
    )
    new_item_name = forms.CharField(
        label="...or create a new stock item (name)", max_length=200, required=False,
    )
    new_item_unit = forms.ModelChoiceField(
        label="Unit for the new item", queryset=Unit.objects.all(), required=False,
    )
    new_item_category = forms.ModelChoiceField(
        label="Category for the new item", queryset=InventoryCategory.objects.all(), required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["inventory_item"].queryset = InventoryItem.objects.filter(
            is_active=True
        ).order_by("name")
        for name in ("inventory_item", "new_item_name", "new_item_unit", "new_item_category"):
            self.fields[name].widget.attrs.setdefault("class", "form-input")

    def clean_new_item_name(self):
        return (self.cleaned_data.get("new_item_name") or "").strip()

    def clean(self):
        cleaned = super().clean()
        existing = cleaned.get("inventory_item")
        name = cleaned.get("new_item_name")
        if existing and name:
            raise ValidationError(
                "Pick either an existing stock item or a new one, not both."
            )
        if name:
            if not cleaned.get("new_item_unit") or not cleaned.get("new_item_category"):
                raise ValidationError("A new stock item needs a category and a unit.")
            match = InventoryItem.objects.filter(name__iexact=name).first()
            if match:
                raise ValidationError(
                    f"'{name}' already exists in stock — choose it under "
                    "'Book into stock' instead of creating a duplicate."
                )
        return cleaned

    def book(self, user=None):
        """Return the InventoryItem chosen/created, or None for no explicit booking."""
        if not self.is_valid():
            return None
        if self.cleaned_data.get("inventory_item"):
            return self.cleaned_data["inventory_item"]
        name = self.cleaned_data.get("new_item_name")
        if not name:
            return None
        return InventoryItem.objects.create(
            name=name,
            category=self.cleaned_data["new_item_category"],
            unit=self.cleaned_data["new_item_unit"],
            quantity=0,
            created_by=user,
        )
