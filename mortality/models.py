from django.conf import settings
from django.db import models


class MortalityRecord(models.Model):
    flock = models.ForeignKey(
        "flocks.FlockBatch", on_delete=models.CASCADE, related_name="mortality_records"
    )
    date_recorded = models.DateField()
    quantity = models.PositiveIntegerField()
    cause_of_death = models.CharField(max_length=200, blank=True, null=True)
    symptoms = models.TextField(blank=True, null=True)
    action_taken = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mortality Record"
        verbose_name_plural = "Mortality Records"
        ordering = ["-date_recorded"]

    def __str__(self):
        return f"{self.flock.batch_number} - {self.quantity} died ({self.date_recorded})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.flock:
            total_mortality = MortalityRecord.objects.filter(
                flock=self.flock
            ).aggregate(total=models.Sum("quantity"))["total"]
            self.flock.current_quantity = self.flock.quantity - (total_mortality or 0)
            self.flock.save()
