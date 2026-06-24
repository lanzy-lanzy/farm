from django.conf import settings
from django.db import models


class Buyer(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    buyer_type = models.CharField(
        max_length=50,
        choices=[
            ("individual", "Individual"),
            ("business", "Business"),
            ("wholesale", "Wholesale"),
            ("retail", "Retail"),
        ],
        default="individual",
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Buyer"
        verbose_name_plural = "Buyers"
        ordering = ["name"]

    def __str__(self):
        return self.name
