from django import forms

from .models import FlockBatch


class FlockBatchForm(forms.ModelForm):
    class Meta:
        model = FlockBatch
        fields = [
            "batch_number",
            "breed",
            "quantity",
            "age_days",
            "source",
            "date_acquired",
            "growing_stage",
            "status",
            "notes",
        ]
        widgets = {
            "batch_number": forms.TextInput(attrs={"class": "form-input"}),
            "breed": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "age_days": forms.NumberInput(attrs={"class": "form-input"}),
            "source": forms.TextInput(attrs={"class": "form-input"}),
            "date_acquired": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "growing_stage": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
        }
