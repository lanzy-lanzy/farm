from django.conf import settings
from django.db import models


class InventoryCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Inventory Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class InventoryItem(models.Model):
    category = models.ForeignKey(
        InventoryCategory, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="items")
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
    )
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_purchased = models.DateField(blank=True, null=True)
    expiration_date = models.DateField(blank=True, null=True)
    reorder_level = models.DecimalField(
        max_digits=10, decimal_places=2, default=10, help_text="Minimum quantity before alert"
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit.abbreviation})"

    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    def is_expired(self):
        if self.expiration_date:
            from django.utils import timezone

            return self.expiration_date <= timezone.now().date()
        return False


class InventoryTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("in", "Stock In"),
        ("out", "Stock Out"),
        ("adjustment", "Adjustment"),
    ]

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.item.name}"

    def save(self, *args, **kwargs):
        if self.transaction_type == "in":
            self.item.quantity += self.quantity
        elif self.transaction_type == "out":
            self.item.quantity -= self.quantity
        elif self.transaction_type == "adjustment":
            self.item.quantity = self.quantity
        self.item.save()
        super().save(*args, **kwargs)
