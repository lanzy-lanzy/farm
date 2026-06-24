from django import forms

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
