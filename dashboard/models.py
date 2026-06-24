from django.conf import settings
from django.db import models


class FarmProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="farm_profile"
    )
    farm_name = models.CharField(max_length=200)
    location = models.CharField(max_length=300)
    farm_size = models.CharField(max_length=100, blank=True, null=True)
    farm_type = models.CharField(
        max_length=50,
        choices=[
            ("layer", "Layer Farm"),
            ("broiler", "Broiler Farm"),
            ("mixed", "Mixed Farm"),
        ],
        default="mixed",
    )
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to="farm_logos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Farm Profile"
        verbose_name_plural = "Farm Profiles"

    def __str__(self):
        return self.farm_name
