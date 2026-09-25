from django import forms

from .models import MedicineRecord


class MedicineRecordForm(forms.ModelForm):
    class Meta:
        model = MedicineRecord
        fields = [
            "flock",
            "medicine_item",
            "medicine_type",
            "medicine_name",
            "dosage",
            "quantity_used",
            "date_administered",
            "administration_route",
            "next_schedule",
            "remarks",
        ]
        widgets = {
            "flock": forms.Select(attrs={"class": "form-input"}),
            "medicine_item": forms.Select(attrs={"class": "form-input"}),
            "medicine_type": forms.Select(attrs={"class": "form-input"}),
            "medicine_name": forms.TextInput(attrs={"class": "form-input"}),
            "dosage": forms.TextInput(attrs={"class": "form-input"}),
            "quantity_used": forms.NumberInput(attrs={"class": "form-input"}),
            "date_administered": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "administration_route": forms.Select(attrs={"class": "form-input"}),
            "next_schedule": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "remarks": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("medicine_item")
        quantity = cleaned.get("quantity_used")
        if (
            self.instance.pk is None
            and item is not None
            and quantity is not None
            and item.quantity < quantity
        ):
            self.add_error(
                "quantity_used",
                f"Only {item.quantity} {item.unit.abbreviation} of {item.name} in stock.",
            )
        return cleaned
