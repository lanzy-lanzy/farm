from django.db import models as djm
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from buyers.models import Buyer, OrderRequest
from deaths.models import DeathRecord
from eggs.models import EggProduction
from expenses.models import ExpenseRecord
from feeding.models import FeedingRecord
from flocks.models import FlockBatch
from inventory.models import InventoryItem
from medicine.models import MedicineRecord
from notifications.models import Notification
from sales.models import SalesRecord
from suppliers.models import DeliveryNotice, Supplier

from .permissions import IsAdminOrOwner, IsInternalUser, IsOwner
from .serializers import (
    BuyerSerializer,
    EggProductionSerializer,
    ExpenseRecordSerializer,
    FeedingRecordSerializer,
    FlockBatchSerializer,
    InventoryItemSerializer,
    MedicineRecordSerializer,
    DeathRecordSerializer,
    NotificationSerializer,
    SalesRecordSerializer,
    SupplierSerializer,
)


def _apply_date_range(queryset, request, field):
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lte": end})
    return queryset


def _total(queryset, field):
    return queryset.aggregate(total=Sum(field))["total"] or 0


class ReadOnlyOwnerViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsOwner]


class FlockViewSet(ReadOnlyOwnerViewSet):
    serializer_class = FlockBatchSerializer

    def get_queryset(self):
        qs = FlockBatch.objects.select_related("created_by").order_by("-created_at")
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


class InventoryItemViewSet(ReadOnlyOwnerViewSet):
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        qs = InventoryItem.objects.select_related("category", "unit", "supplier").order_by("name")
        if self.request.query_params.get("low_stock"):
            qs = qs.filter(is_active=True, quantity__lte=djm.F("reorder_level"))
        return qs


class EggProductionViewSet(ReadOnlyOwnerViewSet):
    serializer_class = EggProductionSerializer

    def get_queryset(self):
        qs = EggProduction.objects.select_related("flock").order_by("-production_date")
        return _apply_date_range(qs, self.request, "production_date")


class DeathViewSet(ReadOnlyOwnerViewSet):
    serializer_class = DeathRecordSerializer

    def get_queryset(self):
        qs = DeathRecord.objects.select_related("flock").order_by("-date_recorded")
        return _apply_date_range(qs, self.request, "date_recorded")


class FeedingViewSet(ReadOnlyOwnerViewSet):
    serializer_class = FeedingRecordSerializer

    def get_queryset(self):
        qs = FeedingRecord.objects.select_related("flock", "feed_item").order_by("-feeding_date")
        qs = _apply_date_range(qs, self.request, "feeding_date")
        flock = self.request.query_params.get("flock")
        if flock:
            qs = qs.filter(flock_id=flock)
        return qs


class MedicineViewSet(ReadOnlyOwnerViewSet):
    serializer_class = MedicineRecordSerializer

    def get_queryset(self):
        qs = MedicineRecord.objects.select_related("flock", "medicine_item").order_by("-date_administered")
        return _apply_date_range(qs, self.request, "date_administered")


class SalesViewSet(ReadOnlyOwnerViewSet):
    serializer_class = SalesRecordSerializer

    def get_queryset(self):
        qs = SalesRecord.objects.select_related("flock", "buyer").order_by("-date_sold")
        return _apply_date_range(qs, self.request, "date_sold")


class ExpenseViewSet(ReadOnlyOwnerViewSet):
    serializer_class = ExpenseRecordSerializer

    def get_queryset(self):
        qs = ExpenseRecord.objects.select_related("category").order_by("-expense_date")
        return _apply_date_range(qs, self.request, "expense_date")


class SupplierViewSet(ReadOnlyOwnerViewSet):
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.order_by("name")


class BuyerViewSet(ReadOnlyOwnerViewSet):
    serializer_class = BuyerSerializer
    queryset = Buyer.objects.order_by("name")


class NotificationViewSet(ReadOnlyOwnerViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        # Unread first (is_read ascending puts False ahead of True) so the newest
        # still-actionable items land on the first page.
        qs = Notification.objects.filter(user=self.request.user).order_by("is_read", "-created_at")
        if self.request.query_params.get("unread"):
            qs = qs.filter(is_read=False)
        return qs


class LowStockInventoryView(ListAPIView):
    permission_classes = [IsOwner]
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        return (
            InventoryItem.objects.filter(is_active=True, quantity__lte=djm.F("reorder_level"))
            .select_related("category", "unit", "supplier")
            .order_by("quantity")
        )


class NotificationUnreadCountView(APIView):
    permission_classes = [IsOwner]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread": count})


class SummaryView(APIView):
    """Dashboard KPIs, mirroring dashboard/views.index so the app matches the web numbers."""

    permission_classes = [IsInternalUser]

    def get(self, request):
        today = timezone.localdate()
        week_ago = today - timezone.timedelta(days=7)
        month_ago = today - timezone.timedelta(days=30)
        # Staff triages the portal queues but may not grant portal access, so the verification
        # backlog is only counted for accounts that can actually act on it.
        may_verify = IsAdminOrOwner().has_permission(request, self)
        pending_verifications = (
            Buyer.objects.filter(verification_status="pending").count()
            + Supplier.objects.filter(verification_status="pending").count()
        ) if may_verify else None

        return Response({
            "total_chickens": _total(FlockBatch.objects.filter(status="active"), "current_quantity"),
            "total_flocks": FlockBatch.objects.filter(status="active").count(),
            "low_stock_items": InventoryItem.objects.filter(is_active=True, quantity__lte=djm.F("reorder_level")).count(),
            "expired_items": InventoryItem.objects.filter(is_active=True, expiration_date__lte=today, expiration_date__isnull=False).count(),
            "today_eggs": _total(EggProduction.objects.filter(production_date=today), "total_eggs"),
            "week_eggs": _total(EggProduction.objects.filter(production_date__gte=week_ago), "total_eggs"),
            "month_eggs": _total(EggProduction.objects.filter(production_date__gte=month_ago), "total_eggs"),
            "total_mortality": _total(DeathRecord.objects.filter(date_recorded__gte=month_ago), "quantity"),
            "week_sales": _total(SalesRecord.objects.filter(date_sold__gte=week_ago), "total_amount"),
            "month_sales": _total(SalesRecord.objects.filter(date_sold__gte=month_ago), "total_amount"),
            "week_expenses": _total(ExpenseRecord.objects.filter(expense_date__gte=week_ago), "amount"),
            "month_expenses": _total(ExpenseRecord.objects.filter(expense_date__gte=month_ago), "amount"),
            "unread_notifications": Notification.objects.filter(user=request.user, is_read=False).count(),
            "open_requests": OrderRequest.objects.filter(
                status__in=["submitted", "under_review", "quoted", "accepted"]
            ).count(),
            "open_deliveries": DeliveryNotice.objects.filter(status__in=["announced", "confirmed"]).count(),
            "pending_verifications": pending_verifications,
        })


class TrendsView(APIView):
    """Rolling 7-day egg production and mortality series for charts."""

    permission_classes = [IsInternalUser]

    def get(self, request):
        today = timezone.localdate()
        eggs, mortality = [], []
        for i in range(6, -1, -1):
            day = today - timezone.timedelta(days=i)
            eggs.append({"date": day.strftime("%b %d"), "eggs": _total(EggProduction.objects.filter(production_date=day), "total_eggs")})
            mortality.append({"date": day.strftime("%b %d"), "deaths": _total(DeathRecord.objects.filter(date_recorded=day), "quantity")})
        return Response({"egg_trend": eggs, "mortality_trend": mortality})
