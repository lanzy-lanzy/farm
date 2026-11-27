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
        ("submitted", "Pending Approval"),
        ("approved", "Approved"),
        ("processing", "Processing"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("under_review", "Under Review"),
        ("quoted", "Quoted"),
        ("accepted", "Accepted by Buyer"),
        ("converted", "Completed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    OPEN_STATUSES = (
        "submitted",
        "under_review",
        "quoted",
        "approved",
        "accepted",
        "processing",
        "out_for_delivery",
        "delivered",
    )

    QUEUE_FILTER_STATUSES = [
        ("submitted", "Pending Approval"),
        ("approved", "Approved"),
        ("processing", "Processing"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
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
    requested_date = models.DateField(null=True, blank=True)
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

    def can_approve(self):
        return self.status in ("submitted", "under_review")

    def can_start_processing(self):
        return self.status == "approved"

    def can_mark_out_for_delivery(self):
        return self.status == "processing"

    def can_mark_delivered(self):
        return self.status in ("approved", "accepted", "processing", "out_for_delivery")

    def can_confirm_received(self):
        return self.status == "out_for_delivery"

    def can_quote(self):
        return self.status in ("submitted", "under_review")

    def can_requote(self):
        return self.status == "quoted"

    def can_accept(self):
        return self.status == "quoted" and not self.is_stale

    def can_convert(self):
        return self.status in ("accepted", "approved", "delivered") and self.sales_record_id is None

    def timeline(self):
        steps = [
            ("submitted", "Pending Approval"),
            ("approved", "Approved"),
            ("processing", "Processing"),
            ("out_for_delivery", "Out for Delivery"),
            ("delivered", "Delivered"),
            ("completed", "Completed"),
        ]
        status_to_idx = {
            "submitted": 0,
            "under_review": 0,
            "quoted": 0,
            "approved": 1,
            "processing": 2,
            "out_for_delivery": 3,
            "accepted": 4,
            "delivered": 4,
            "completed": 5,
            "converted": 5,
        }
        closed_bad = self.status in ("rejected", "cancelled")
        if closed_bad:
            idx = 1 if self.quoted_unit_price is not None else 0
        else:
            idx = status_to_idx.get(self.status, 0)
        timeline = []
        for i, (_, label) in enumerate(steps):
            if i < idx:
                state = "done"
            elif i == idx:
                state = "dead" if closed_bad else ("done" if i == len(steps) - 1 else "current")
            else:
                state = "pending"
            timeline.append((label, state))
        return timeline
