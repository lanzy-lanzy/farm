from django.conf import settings
from django.db import models


class FeedingRecord(models.Model):
    flock = models.ForeignKey(
        "flocks.FlockBatch", on_delete=models.CASCADE, related_name="feeding_records"
    )
    feed_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="feeding_records",
    )
    quantity_used = models.DecimalField(max_digits=10, decimal_places=2)
    feeding_date = models.DateField()
    feeding_time = models.TimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feeding Record"
        verbose_name_plural = "Feeding Records"
        ordering = ["-feeding_date", "-feeding_time"]

    def __str__(self):
        return f"{self.flock.batch_number} - {self.feed_item.name} ({self.feeding_date})"

    def save(self, *args, **kwargs):
        from inventory.models import InventoryTransaction

        super().save(*args, **kwargs)
        if not InventoryTransaction.objects.filter(
            reference=f"Feeding Record #{self.pk}"
        ).exists():
            InventoryTransaction.objects.create(
                item=self.feed_item,
                transaction_type="out",
                quantity=self.quantity_used,
                reference=f"Feeding Record #{self.pk}",
                created_by=self.recorded_by,
            )
