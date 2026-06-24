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
