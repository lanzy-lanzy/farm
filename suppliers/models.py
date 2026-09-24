from django.conf import settings
from django.db import models


class Supplier(models.Model):
    VERIFICATION_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    PAYMENT_TERMS_CHOICES = [
        ("cod", "Cash on Delivery"),
        ("net15", "Net 15"),
        ("net30", "Net 30"),
    ]

    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    supplies = models.CharField(
        max_length=300, blank=True, null=True, help_text="What they supply"
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_suppliers",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier",
    )
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default="pending"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_suppliers",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    payment_terms = models.CharField(
        max_length=20, choices=PAYMENT_TERMS_CHOICES, default="cod"
    )
    dti_registration = models.CharField(
        max_length=50, blank=True, null=True, help_text="Optional DTI registration no."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Deactivating the contact record must revoke the linked portal login.
        if self.user_id and not self.is_active and self.user.is_active:
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])


class SupplyItem(models.Model):
    AVAILABILITY_CHOICES = [
        ("in_stock", "In Stock"),
        ("made_to_order", "Made to Order"),
        ("seasonal", "Seasonal"),
    ]

    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="supply_items"
    )
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.ForeignKey(
        "inventory.Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supply_items",
    )
    availability = models.CharField(
        max_length=20, choices=AVAILABILITY_CHOICES, default="in_stock"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Supply Item"
        verbose_name_plural = "Supply Items"
        ordering = ["name"]

    def __str__(self):
        return self.name


class DeliveryNotice(models.Model):
    STATUS_CHOICES = [
        ("announced", "Announced"),
        ("received", "Received"),
        ("rejected", "Rejected"),
    ]

    ORIGIN_CHOICES = [
        ("supplier", "Supplier Announced"),
        ("farm", "Farm Ordered"),
    ]

    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="delivery_notices"
    )
    origin = models.CharField(
        max_length=10, choices=ORIGIN_CHOICES, default="supplier"
    )
    supply_item = models.ForeignKey(
        SupplyItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_notices",
    )
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    expected_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="announced")
    supplier_note = models.TextField(blank=True, null=True)
    expense_record = models.OneToOneField(
        "expenses.ExpenseRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_notice",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_deliveries",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_delivery_notices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Notice"
        verbose_name_plural = "Delivery Notices"
        ordering = ["-expected_date"]

    def __str__(self):
        return f"{self.supplier.name} - {self.description} ({self.expected_date})"

    @property
    def is_supplier_cancellable(self):
        return self.origin == "supplier" and self.status == "announced"

    @property
    def is_farm_order_open(self):
        return self.origin == "farm" and self.status == "announced"
