from django.conf import settings
from django.db import models
from django.utils import timezone


class Buyer(models.Model):
    VERIFICATION_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    buyer_type = models.CharField(
        max_length=50,
        choices=[
            ("individual", "Individual"),
            ("business", "Business"),
            ("wholesale", "Wholesale"),
            ("retail", "Retail"),
        ],
        default="individual",
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_buyers",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buyer",
    )
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default="pending"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_buyers",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Buyer"
        verbose_name_plural = "Buyers"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def outstanding_balance(self):
        from django.db.models import Sum, F

        agg = self.sales_records.aggregate(
            total=Sum(F("total_amount") - F("amount_paid"))
        )
        return agg["total"] or 0

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Deactivating the contact record must revoke the linked portal login.
        if self.user_id and not self.is_active and self.user.is_active:
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])


class OrderRequest(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("quoted", "Quoted"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("converted", "Converted to Sale"),
        ("cancelled", "Cancelled"),
    ]

    PRODUCT_CHOICES = [
        ("eggs", "Eggs"),
        ("chicken", "Live Chicken"),
        ("dressed", "Dressed Chicken"),
        ("manure", "Manure"),
        ("other", "Other"),
    ]

    SOURCE_CHOICES = [
        ("portal", "Buyer Portal"),
        ("staff", "On Behalf (Staff)"),
    ]

    request_number = models.CharField(max_length=30, unique=True, blank=True)
    buyer = models.ForeignKey(
        Buyer, on_delete=models.CASCADE, related_name="order_requests"
    )
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default="portal"
    )
    product_type = models.CharField(max_length=20, choices=PRODUCT_CHOICES)
    product_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    requested_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    requested_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    quoted_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    staff_note = models.TextField(blank=True, null=True)
    sales_record = models.OneToOneField(
        "sales.SalesRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_request",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order Request"
        verbose_name_plural = "Order Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.request_number} - {self.product_name}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            year = timezone.localdate().year
            last = (
                OrderRequest.objects.filter(request_number__startswith=f"REQ-{year}-")
                .order_by("-request_number")
                .values_list("request_number", flat=True)
                .first()
            )
            seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
            self.request_number = f"REQ-{year}-{seq:04d}"
        super().save(*args, **kwargs)

    @property
    def effective_unit_price(self):
        return self.quoted_unit_price if self.quoted_unit_price is not None else self.requested_unit_price

    @property
    def estimated_total(self):
        if self.effective_unit_price is None:
            return None
        return self.quantity * self.effective_unit_price

    @property
    def is_cancellable(self):
        return self.status in ("submitted", "under_review", "quoted")

    @property
    def is_stale(self):
        """A quote older than the configured window must be re-quoted before acceptance."""
        if self.status != "quoted":
            return False
        from django.conf import settings

        days = getattr(settings, "ORDER_REQUEST_QUOTE_STALE_DAYS", 7)
        return timezone.now() - self.updated_at > timezone.timedelta(days=days)

    def can_quote(self):
        return self.status in ("submitted", "under_review")

    def can_requote(self):
        return self.status == "quoted"

    def can_accept(self):
        return self.status == "quoted" and not self.is_stale

    def can_convert(self):
        return self.status == "accepted" and self.sales_record_id is None

    def timeline(self):
        steps = ["submitted", "under_review", "quoted", "accepted", "converted"]
        labels = dict(self.STATUS_CHOICES)
        timeline = []
        if self.status in ("rejected", "cancelled"):
            idx = 2 if self.quoted_unit_price is not None else 1
        else:
            idx = steps.index(self.status) if self.status in steps else 0
        for i, step in enumerate(steps):
            if i < idx:
                state = "done"
            elif i == idx:
                state = "dead" if self.status in ("rejected", "cancelled") else "current"
            else:
                state = "pending"
            timeline.append((labels[step], state))
        return timeline
