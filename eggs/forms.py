from django import forms

from .models import EggProduction


class EggProductionForm(forms.ModelForm):
    class Meta:
        model = EggProduction
        fields = [
            "flock",
            "production_date",
            "good_eggs",
            "cracked_eggs",
            "rejected_eggs",
            "remarks",
        ]
        widgets = {
            "flock": forms.Select(attrs={"class": "form-input"}),
            "production_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "good_eggs": forms.NumberInput(attrs={"class": "form-input"}),
            "cracked_eggs": forms.NumberInput(attrs={"class": "form-input"}),
            "rejected_eggs": forms.NumberInput(attrs={"class": "form-input"}),
            "remarks": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }
