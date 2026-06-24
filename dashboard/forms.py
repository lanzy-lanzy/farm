from django import forms

from .models import FarmProfile


class FarmProfileForm(forms.ModelForm):
    class Meta:
        model = FarmProfile
        fields = [
            "farm_name",
            "location",
            "farm_size",
            "farm_type",
            "contact_number",
            "email",
            "logo",
        ]
        widgets = {
            "farm_name": forms.TextInput(attrs={"class": "form-input"}),
            "location": forms.TextInput(attrs={"class": "form-input"}),
            "farm_size": forms.TextInput(attrs={"class": "form-input"}),
            "farm_type": forms.Select(attrs={"class": "form-input"}),
            "contact_number": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "logo": forms.FileInput(attrs={"class": "form-input"}),
        }
