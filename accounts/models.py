from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("owner", "Farm Owner"),
        ("staff", "Staff/Caretaker"),
        ("buyer", "Buyer"),
        ("supplier", "Supplier"),
    ]

    INTERNAL_ROLES = ("admin", "owner", "staff")
    EXTERNAL_ROLES = ("buyer", "supplier")

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    def is_admin_user(self):
        return self.role == "admin" or self.is_superuser

    def is_owner(self):
        return self.role == "owner"

    def is_staff_member(self):
        return self.role == "staff"

    def is_external(self):
        return self.role in self.EXTERNAL_ROLES

    def is_internal(self):
        return self.role in self.INTERNAL_ROLES or self.is_superuser
