from django.conf import settings
from django.db import models


class EggProduction(models.Model):
    flock = models.ForeignKey(
        "flocks.FlockBatch", on_delete=models.CASCADE, related_name="egg_productions"
    )
    production_date = models.DateField()
    good_eggs = models.PositiveIntegerField(default=0)
    cracked_eggs = models.PositiveIntegerField(default=0)
    rejected_eggs = models.PositiveIntegerField(default=0)
    total_eggs = models.PositiveIntegerField(default=0)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Egg Production"
        verbose_name_plural = "Egg Productions"
        ordering = ["-production_date"]
        unique_together = ["flock", "production_date"]

    def __str__(self):
        return f"{self.flock.batch_number} - {self.total_eggs} eggs ({self.production_date})"

    def save(self, *args, **kwargs):
        self.total_eggs = self.good_eggs + self.cracked_eggs + self.rejected_eggs
        super().save(*args, **kwargs)

    def production_rate(self):
        if self.flock and self.flock.current_quantity:
            return round(
                (self.total_eggs / self.flock.current_quantity) * 100, 2
            )
        return 0
