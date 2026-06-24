from django.conf import settings
from django.db import models
from django.utils import timezone


class FlockBatch(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("sold", "Sold"),
        ("depleted", "Depleted"),
        ("culled", "Culled"),
    ]

    STAGE_CHOICES = [
        ("chick", "Chick"),
        ("grower", "Grower"),
        ("layer", "Layer"),
        ("broiler", "Broiler"),
    ]

    batch_number = models.CharField(max_length=50, unique=True)
    breed = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    current_quantity = models.PositiveIntegerField(blank=True, null=True)
    age_days = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=200, blank=True, null=True)
    date_acquired = models.DateField()
    growing_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="chick")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Flock Batch"
        verbose_name_plural = "Flock Batches"
        ordering = ["-date_acquired"]

    def __str__(self):
        return f"{self.batch_number} - {self.breed}"

    def save(self, *args, **kwargs):
        if self.current_quantity is None:
            self.current_quantity = self.quantity
        super().save(*args, **kwargs)

    def remaining_stock(self):
        return self.current_quantity or self.quantity

    def mortality_count(self):
        return self.mortality_records.aggregate(total=models.Sum("quantity"))["total"] or 0

    def sold_count(self):
        return self.sales_records.aggregate(total=models.Sum("quantity"))["total"] or 0
