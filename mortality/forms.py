from django import forms

from .models import MortalityRecord


class MortalityRecordForm(forms.ModelForm):
    class Meta:
        model = MortalityRecord
        fields = [
            "flock",
            "date_recorded",
            "quantity",
            "cause_of_death",
            "symptoms",
            "action_taken",
            "remarks",
        ]
        widgets = {
            "flock": forms.Select(attrs={"class": "form-input"}),
            "date_recorded": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "cause_of_death": forms.TextInput(attrs={"class": "form-input"}),
            "symptoms": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "action_taken": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "remarks": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }
