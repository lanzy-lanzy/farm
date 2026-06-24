from django.conf import settings
from django.db import models


class MedicineRecord(models.Model):
    TYPE_CHOICES = [
        ("medicine", "Medicine"),
        ("vaccine", "Vaccine"),
        ("vitamin", "Vitamin"),
    ]

    flock = models.ForeignKey(
        "flocks.FlockBatch", on_delete=models.CASCADE, related_name="medicine_records"
    )
    medicine_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="medicine_records",
        blank=True,
        null=True,
    )
    medicine_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="medicine")
    medicine_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    quantity_used = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    date_administered = models.DateField()
    administration_route = models.CharField(
        max_length=50,
        choices=[
            ("oral", "Oral"),
            ("injection", "Injection"),
            ("spray", "Spray"),
            ("water", "In Water"),
            ("other", "Other"),
        ],
        default="oral",
    )
    next_schedule = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medicine Record"
        verbose_name_plural = "Medicine Records"
        ordering = ["-date_administered"]

    def __str__(self):
        return f"{self.medicine_name} - {self.flock.batch_number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.medicine_item and self.quantity_used > 0:
            from inventory.models import InventoryTransaction

            if not InventoryTransaction.objects.filter(
                reference=f"Medicine Record #{self.pk}"
            ).exists():
                InventoryTransaction.objects.create(
                    item=self.medicine_item,
                    transaction_type="out",
                    quantity=self.quantity_used,
                    reference=f"Medicine Record #{self.pk}",
                    created_by=self.recorded_by,
                )
