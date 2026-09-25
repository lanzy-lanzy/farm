from django.conf import settings
from django.db import models


class SalesRecord(models.Model):
    PRODUCT_CHOICES = [
        ("eggs", "Eggs"),
        ("chicken", "Live Chicken"),
        ("dressed", "Dressed Chicken"),
        ("manure", "Manure"),
        ("other", "Other"),
    ]

    PAYMENT_CHOICES = [
        ("paid", "Paid"),
        ("pending", "Pending"),
        ("partial", "Partial"),
    ]

    product_type = models.CharField(max_length=20, choices=PRODUCT_CHOICES)
    flock = models.ForeignKey(
        "flocks.FlockBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_records",
    )
    buyer = models.ForeignKey(
        "buyers.Buyer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_records",
    )
    product_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_sold = models.DateField()
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="paid")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sales Record"
        verbose_name_plural = "Sales Records"
        ordering = ["-date_sold"]

    def __str__(self):
        return f"{self.product_name} - {self.total_amount} ({self.date_sold})"

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def balance(self):
        return self.total_amount - self.amount_paid
