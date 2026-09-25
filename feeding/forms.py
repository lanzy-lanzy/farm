from django import forms

from .models import FeedingRecord


class FeedingRecordForm(forms.ModelForm):
    class Meta:
        model = FeedingRecord
        fields = [
            "flock",
            "feed_item",
            "quantity_used",
            "feeding_date",
            "feeding_time",
            "remarks",
        ]
        widgets = {
            "flock": forms.Select(attrs={"class": "form-input"}),
            "feed_item": forms.Select(attrs={"class": "form-input"}),
            "quantity_used": forms.NumberInput(attrs={"class": "form-input"}),
            "feeding_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "feeding_time": forms.TimeInput(attrs={"class": "form-input", "type": "time"}),
            "remarks": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("feed_item")
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
