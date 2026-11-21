from django.conf import settings
from django.db import models
from django.templatetags.static import static


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


class Product(models.Model):
    """Farm catalog offered to buyer portal accounts; pre-fills order requests."""

    DEFAULT_STATIC_IMAGES = {
        "eggs": "images/products/eggs_large.jpg",
        "chicken": "images/products/live_chicken.jpg",
        "dressed": "images/products/dressed_chicken.jpg",
        "manure": "images/products/organic_manure.jpg",
        "other": "images/products/eggs_medium.jpg",
    }

    name = models.CharField(max_length=200)
    product_type = models.CharField(max_length=20, choices=SalesRecord.PRODUCT_CHOICES)
    unit_label = models.CharField(
        max_length=50, default="pc", help_text='What one quantity unit means, e.g. "tray", "kg", "sack".'
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True,
        help_text="Optional custom product photo. If omitted, a bundled farm photo is used.",
    )
    static_image = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Bundled static asset path under /static/ (persists across redeploys).",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["product_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.unit_label})"

    def default_static_path(self) -> str:
        if self.product_type == "eggs":
            lower = (self.name or "").lower()
            if "small" in lower or "pewee" in lower or "pullet" in lower:
                return "images/products/eggs_small.jpg"
            if "medium" in lower:
                return "images/products/eggs_medium.jpg"
            if "extra" in lower or "xl" in lower or "jumbo" in lower:
                return "images/products/eggs_xl.jpg"
            return "images/products/eggs_large.jpg"
        return self.DEFAULT_STATIC_IMAGES.get(
            self.product_type, "images/products/eggs_large.jpg"
        )

    @property
    def image_url(self) -> str:
        if self.image:
            try:
                return self.image.url
            except ValueError:
                pass
        path = self.static_image or self.default_static_path()
        return static(path)
