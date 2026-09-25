from django import forms

from .models import Notification


class NotificationForm(forms.ModelForm):
    """The part of a notification a person may change: what it says and where it leads.

    The recipient is deliberately absent — editing works on the copy sitting in the
    signed-in user's own inbox, never on someone else's.
    """

    class Meta:
        model = Notification
        fields = ["notification_type", "title", "message", "link"]
        widgets = {
            "notification_type": forms.Select(attrs={"class": "form-input"}),
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Vaccination due for B-2401"}
            ),
            "message": forms.Textarea(
                attrs={"class": "form-input", "rows": 3, "placeholder": "What the team needs to do"}
            ),
            "link": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "/medicine/"}
            ),
        }

    def clean_link(self):
        link = (self.cleaned_data.get("link") or "").strip()
        if not link:
            return ""
        # A notification click should land on a farm page. Protocol-relative and
        # absolute URLs are refused here so nothing can send staff off-site.
        if not link.startswith("/") or link.startswith("//"):
            raise forms.ValidationError(
                "Use an in-app path such as /inventory/ — a full web address is not allowed."
            )
        return link

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A required select arrives with an empty "---------" option preselected, which
        # silently blocks the send until the user notices the untouched dropdown. Drop
        # the placeholder so a real subject is always chosen.
        self.fields["notification_type"].choices = [
            choice for choice in self.fields["notification_type"].choices if choice[0]
        ]


class NotificationComposeForm(NotificationForm):
    """Creating a notification from the inbox: post it to the whole team or keep it as a reminder."""

    AUDIENCE_CHOICES = [
        ("team", "The whole farm team"),
        ("me", "Just me (a reminder)"),
    ]

    audience = forms.ChoiceField(
        choices=AUDIENCE_CHOICES,
        initial="team",
        widget=forms.Select(attrs={"class": "form-input"}),
        help_text="Team notices appear in every admin, owner and staff inbox.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Manual notices posted from the inbox are general updates, so start there
        # instead of on "Low Stock Alert" merely because it sorts first.
        self.fields["notification_type"].initial = "activity"
