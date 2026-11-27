from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from buyers.models import Buyer
from suppliers.models import Supplier

from .models import User


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Invalid username or password. Please try again.",
        "inactive": "This account is inactive. Please contact the farm administrator.",
        "pending_approval": (
            "Your account is pending administrator approval. "
            "You will be able to sign in once an administrator approves your registration."
        ),
        "rejected": "Your registration was not approved. Please contact the farm administrator.",
    }

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "Username"}
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-input", "placeholder": "Password"}
        )
    )

    def _raise_external_status_error(self, user):
        if user.is_external():
            profile = getattr(user, user.role, None)
            if profile is not None:
                if profile.verification_status == "pending":
                    raise ValidationError(
                        self.error_messages["pending_approval"],
                        code="pending_approval",
                    )
                if profile.verification_status == "rejected":
                    reason = (profile.rejection_reason or "").strip()
                    if reason:
                        raise ValidationError(
                            f"Your registration was not approved. Reason: {reason} "
                            "Please contact the farm administrator.",
                            code="rejected",
                        )
                    raise ValidationError(
                        self.error_messages["rejected"],
                        code="rejected",
                    )
                if not profile.is_active:
                    raise ValidationError(
                        self.error_messages["inactive"],
                        code="inactive",
                    )
        raise ValidationError(
            self.error_messages["inactive"],
            code="inactive",
        )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                # ModelBackend returns None for inactive users; check whether this is a
                # pending/rejected/inactive account with valid credentials so we can show
                # a helpful message instead of a generic invalid-password error.
                try:
                    candidate = User._default_manager.get_by_natural_key(username)
                except User.DoesNotExist:
                    candidate = None
                if (
                    candidate is not None
                    and not candidate.is_active
                    and candidate.check_password(password)
                ):
                    self._raise_external_status_error(candidate)
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            self._raise_external_status_error(user)
        if user.is_external():
            profile = getattr(user, user.role, None)
            if (
                profile is None
                or profile.verification_status != "approved"
                or not profile.is_active
            ):
                self._raise_external_status_error(user)


class PartnerRegistrationForm(UserCreationForm):
    ROLE_CHOICES = [
        ("buyer", "Buyer"),
        ("supplier", "Supplier"),
    ]

    role = forms.ChoiceField(choices=ROLE_CHOICES, initial="buyer")
    name = forms.CharField(max_length=200, label="Full Name or Business Name")
    contact_person = forms.CharField(
        max_length=100, required=False, label="Contact Person"
    )
    email = forms.EmailField(required=True, label="Email Address")
    phone = forms.CharField(max_length=20, required=False, label="Phone Number")
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Address",
    )
    # Buyer-specific
    buyer_type = forms.ChoiceField(
        choices=Buyer._meta.get_field("buyer_type").choices,
        initial="individual",
        required=False,
        label="Buyer Type",
    )
    # Supplier-specific
    supplies = forms.CharField(
        max_length=300,
        required=False,
        label="Products / Supplies Offered",
    )
    payment_terms = forms.ChoiceField(
        choices=Supplier.PAYMENT_TERMS_CHOICES,
        initial="cod",
        required=False,
        label="Payment Terms",
    )
    dti_registration = forms.CharField(
        max_length=50,
        required=False,
        label="DTI Registration No. (Optional)",
    )

    class Meta:
        model = User
        fields = ["username", "email"]

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if role not in ("buyer", "supplier"):
            raise ValidationError("Please select either Buyer or Supplier.")
        return role

    def save(self, commit=True):
        role = self.cleaned_data["role"]
        name = self.cleaned_data["name"].strip()
        contact_person = (self.cleaned_data.get("contact_person") or "").strip() or None
        phone = (self.cleaned_data.get("phone") or "").strip() or None
        email = self.cleaned_data["email"].strip()
        address = (self.cleaned_data.get("address") or "").strip() or None

        user = super().save(commit=False)
        user.role = role
        user.is_active = False
        user.email = email
        user.phone = phone or ""
        user.address = address or ""
        user.first_name = (contact_person or name)[:30]
        if not commit:
            return user

        user.save()
        if role == "buyer":
            profile = Buyer.objects.create(
                name=name,
                contact_person=contact_person,
                phone=phone,
                email=email,
                address=address,
                buyer_type=self.cleaned_data.get("buyer_type") or "individual",
                user=user,
                verification_status="pending",
                is_active=True,
            )
        else:
            profile = Supplier.objects.create(
                name=name,
                contact_person=contact_person,
                phone=phone,
                email=email,
                address=address,
                supplies=(self.cleaned_data.get("supplies") or "").strip() or None,
                payment_terms=self.cleaned_data.get("payment_terms") or "cod",
                dti_registration=(self.cleaned_data.get("dti_registration") or "").strip() or None,
                user=user,
                verification_status="pending",
                is_active=True,
            )
        return user, profile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "Email"})
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "role", "phone"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-input"}),
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "role": forms.Select(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
        }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "address", "profile_picture"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "profile_picture": forms.FileInput(attrs={"class": "form-input"}),
        }


class AdminUserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "phone",
            "address",
            "is_active",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-input"}),
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "role": forms.Select(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 2}),
        }
