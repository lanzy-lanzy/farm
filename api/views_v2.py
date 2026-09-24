from decimal import Decimal

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from buyers.models import Buyer, OrderRequest
from expenses.models import ExpenseRecord
from inventory.models import Unit
from notifications.models import Notification
from notifications.utils import log_activity, notify_team, notify_user
from sales.models import SalesRecord
from sales.views import credit_block_reason
from suppliers.models import DeliveryNotice, Supplier, SupplyItem

from .permissions import (
    IsAdminOrOwner,
    IsInternalUser,
    IsVerifiedBuyer,
    IsVerifiedPortalUser,
    IsVerifiedSupplier,
)
from .serializers_v2 import (
    BuyerPortalProfileSerializer,
    ChangePasswordSerializer,
    ConvertSaleSerializer,
    DeliveryNoticePortalSerializer,
    DeliveryNoticeStaffSerializer,
    FarmOrderResponseSerializer,
    OrderRequestPortalSerializer,
    OrderRequestStaffSerializer,
    PortalNotificationSerializer,
    PurchaseHistorySerializer,
    QuoteActionSerializer,
    ReceiveExpenseSerializer,
    RejectActionSerializer,
    SalesHistorySerializer,
    SupplierPortalProfileSerializer,
    SupplyItemSerializer,
    SupplyUnitSerializer,
)


class PortalProfileView(APIView):
    """GET/PATCH the requesting external user's own profile."""

    permission_classes = [IsVerifiedPortalUser]

    def get_profile(self, request):
        return getattr(request.user, request.user.role)

    def get(self, request):
        profile = self.get_profile(request)
        serializer = (
            BuyerPortalProfileSerializer(profile)
            if request.user.role == "buyer"
            else SupplierPortalProfileSerializer(profile)
        )
        return Response(serializer.data)

    def patch(self, request):
        profile = self.get_profile(request)
        serializer = (
            BuyerPortalProfileSerializer(profile, data=request.data, partial=True)
            if request.user.role == "buyer"
            else SupplierPortalProfileSerializer(profile, data=request.data, partial=True)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class OrderRequestPortalViewSet(viewsets.ModelViewSet):
    """Buyer-scoped order requests: list, create, retrieve, cancel, accept, decline."""

    permission_classes = [IsVerifiedBuyer]
    serializer_class = OrderRequestPortalSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        if self.request.user.role != "buyer":
            return OrderRequest.objects.none()
        return OrderRequest.objects.filter(buyer=self.request.user.buyer)

    def create(self, request, *args, **kwargs):
        if request.user.role != "buyer":
            return Response({"detail": "Buyer account required."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(buyer=request.user.buyer, created_by=request.user)
        notify_team(
            "order_request",
            f"New order request {order.request_number}",
            f"{order.buyer.name} requested {order.quantity} {order.product_name}.",
            link=f"/sales/requests/{order.pk}/",
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _owned(self, request, pk):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(self.get_queryset(), pk=pk)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self._owned(request, pk)
        if not order.is_cancellable:
            return Response({"detail": "Request can no longer be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        order.status = "cancelled"
        order.save()
        notify_team("order_request", f"Request {order.request_number} cancelled",
                    f"{order.buyer.name} cancelled the request.", link="/sales/requests/")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        order = self._owned(request, pk)
        if not order.can_accept():
            detail = "This quote has expired; ask the farm to re-quote." if order.is_stale else "Only a quoted request can be accepted."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        order.status = "accepted"
        order.save()
        notify_team("order_request", f"Quote accepted for {order.request_number}",
                    f"{order.buyer.name} accepted the quote. Ready to record the sale.",
                    link=f"/sales/requests/{order.pk}/")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        order = self._owned(request, pk)
        if not order.can_accept():
            return Response({"detail": "Only a quoted request can be declined."}, status=status.HTTP_400_BAD_REQUEST)
        order.status = "rejected"
        order.save()
        notify_team("order_request", f"Quote declined for {order.request_number}",
                    f"{order.buyer.name} declined the quote.", link=f"/sales/requests/{order.pk}/")
        return Response(self.get_serializer(order).data)


class SalesHistoryView(ListAPIView):
    """The requesting buyer's own sales records."""

    permission_classes = [IsVerifiedBuyer]
    serializer_class = SalesHistorySerializer

    def get_queryset(self):
        if self.request.user.role != "buyer":
            return SalesRecord.objects.none()
        return SalesRecord.objects.filter(buyer=self.request.user.buyer)


class SupplyItemViewSet(viewsets.ModelViewSet):
    """Supplier-scoped catalog CRUD."""

    permission_classes = [IsVerifiedSupplier]
    serializer_class = SupplyItemSerializer

    def get_queryset(self):
        if self.request.user.role != "supplier":
            return SupplyItem.objects.none()
        return SupplyItem.objects.filter(supplier=self.request.user.supplier)

    def perform_create(self, serializer):
        serializer.save(supplier=self.request.user.supplier)


class SupplyUnitsView(APIView):
    """Reference list of measurement units for the supplier catalog form."""

    permission_classes = [IsVerifiedSupplier]

    def get(self, request):
        units = Unit.objects.all().order_by("name")
        return Response(SupplyUnitSerializer(units, many=True).data)


class DeliveryNoticePortalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsVerifiedSupplier]
    serializer_class = DeliveryNoticePortalSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        if self.request.user.role != "supplier":
            return DeliveryNotice.objects.none()
        return DeliveryNotice.objects.filter(supplier=self.request.user.supplier)

    def create(self, request, *args, **kwargs):
        if request.user.role != "supplier":
            return Response({"detail": "Supplier account required."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notice = serializer.save(supplier=request.user.supplier)
        notify_team(
            "delivery_notice",
            f"Delivery from {notice.supplier.name}",
            f"{notice.quantity} {notice.description} expected on {notice.expected_date}.",
            link="/expenses/deliveries/",
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        notice = self.get_object()
        if not notice.is_supplier_cancellable:
            return Response({"detail": "Only your own announced deliveries can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        notice.status = "rejected"
        note = request.data.get("note")
        if note:
            notice.supplier_note = note
        notice.save()
        notify_team("delivery_notice", f"Delivery cancelled: {notice.description}",
                    f"{notice.supplier.name} cancelled the announced delivery. {note or ''}".strip(),
                    link="/expenses/deliveries/")
        return Response(self.get_serializer(notice).data)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        notice = self.get_object()
        if not notice.is_farm_order_open:
            return Response({"detail": "This farm order can no longer be updated."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = FarmOrderResponseSerializer(notice, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        notice = serializer.save()
        notify_team("delivery_notice", f"Supplier confirmed delivery: {notice.description}",
                    f"{notice.supplier.name} confirmed the farm order for {notice.expected_date}."
                    + (f" Note: {notice.supplier_note}" if notice.supplier_note else ""),
                    link="/expenses/deliveries/")
        return Response(self.get_serializer(notice).data)


class PurchaseHistoryView(ListAPIView):
    permission_classes = [IsVerifiedSupplier]
    serializer_class = PurchaseHistorySerializer

    def get_queryset(self):
        if self.request.user.role != "supplier":
            return ExpenseRecord.objects.none()
        return ExpenseRecord.objects.filter(supplier=self.request.user.supplier)


class InternalOrderRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Staff-side review: list, quote, reject, convert."""

    permission_classes = [IsInternalUser]
    serializer_class = OrderRequestStaffSerializer

    def get_queryset(self):
        qs = OrderRequest.objects.select_related("buyer").order_by("-created_at")
        state = self.request.query_params.get("status")
        if state:
            qs = qs.filter(status=state)
        return qs

    @action(detail=True, methods=["post"])
    def quote(self, request, pk=None):
        order = self.get_object()
        if not order.can_quote():
            return Response({"detail": "Request is not quotable in its current status."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = QuoteActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.quoted_unit_price = serializer.validated_data["quoted_unit_price"]
        order.staff_note = serializer.validated_data.get("staff_note") or order.staff_note
        order.status = "quoted"
        order.save()
        notify_user(order.buyer.user, "order_request", f"Quote ready for {order.request_number}",
                    f"The farm quoted {order.quoted_unit_price} per unit.",
                    link=f"/portal/buyer/requests/{order.pk}/")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        order = self.get_object()
        if order.status in ("converted", "cancelled", "rejected"):
            return Response({"detail": "Request is already closed."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = RejectActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.status = "rejected"
        order.staff_note = serializer.validated_data.get("staff_note") or order.staff_note
        order.save()
        notify_user(order.buyer.user, "order_request", f"Request {order.request_number} declined",
                    order.staff_note or "The farm could not fulfil this request.",
                    link=f"/portal/buyer/requests/{order.pk}/")
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        order = self.get_object()
        if not order.can_convert():
            return Response({"detail": "Only an accepted request can be converted."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ConvertSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        elevated = request.user.is_admin_user() or request.user.is_owner()
        data = serializer.validated_data
        if (
            not elevated
            and order.effective_unit_price is not None
            and data["unit_price"] != order.effective_unit_price
        ):
            return Response({"detail": "Only an owner or administrator may change the accepted quote price."}, status=status.HTTP_400_BAD_REQUEST)
        unpaid = data["quantity"] * data["unit_price"] - data.get("amount_paid", Decimal("0"))
        reason = credit_block_reason(order.buyer, unpaid) if data["payment_status"] != "paid" else None
        if reason and not elevated:
            return Response({"detail": f"Credit limit exceeded — {reason}"}, status=status.HTTP_400_BAD_REQUEST)
        record = serializer.save(recorded_by=request.user, buyer=order.buyer)
        if reason:
            log_activity(request.user, "update", "OrderRequest", order.pk, order.request_number, f"Credit limit override at conversion: {reason}")
        order.sales_record = record
        order.status = "converted"
        order.save()
        notify_user(order.buyer.user, "order_request", f"Order {order.request_number} recorded as sold",
                    f"Sale of {record.quantity} {record.product_name} for {record.total_amount} has been recorded.",
                    link=f"/portal/buyer/requests/{order.pk}/")
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)


class InternalDeliveryNoticeViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsInternalUser]
    serializer_class = DeliveryNoticeStaffSerializer

    def get_queryset(self):
        qs = DeliveryNotice.objects.select_related("supplier", "supply_item").order_by("-expected_date")
        state = self.request.query_params.get("status")
        if state:
            qs = qs.filter(status=state)
        return qs

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        notice = self.get_object()
        if notice.status != "announced":
            return Response({"detail": "Notice is not open."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ReceiveExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(recorded_by=request.user, supplier=notice.supplier)
        notice.status = "received"
        notice.expense_record = record
        notice.received_by = request.user
        notice.save()
        notify_user(notice.supplier.user, "delivery_notice", f"Delivery received: {notice.description}",
                    f"The farm booked {record.description} for {record.amount}.",
                    link="/portal/supplier/history/")
        return Response(self.get_serializer(notice).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        notice = self.get_object()
        if notice.status != "announced":
            return Response({"detail": "Notice is not open."}, status=status.HTTP_400_BAD_REQUEST)
        notice.status = "rejected"
        notice.save()
        notify_user(notice.supplier.user, "delivery_notice", f"Delivery rejected: {notice.description}",
                    request.data.get("note") or "The farm could not accept this delivery.",
                    link="/portal/supplier/deliveries/")
        return Response(self.get_serializer(notice).data)


class PendingVerificationsView(APIView):
    permission_classes = [IsAdminOrOwner]

    @staticmethod
    def _row(profile):
        return {
            "id": profile.pk,
            "name": profile.name,
            "phone": profile.phone,
            "email": profile.email,
            "verification_status": profile.verification_status,
            "has_account": profile.user_id is not None,
            "created_at": profile.created_at,
        }

    def get(self, request):
        buyers = Buyer.objects.filter(verification_status="pending").order_by("-created_at")
        suppliers = Supplier.objects.filter(verification_status="pending").order_by("-created_at")
        return Response({
            "buyers": [self._row(b) for b in buyers],
            "suppliers": [self._row(s) for s in suppliers],
        })


class VerificationActionView(APIView):
    """POST /api/v2/internal/verifications/<buyer|supplier>/<pk>/<approve|reject>/"""

    permission_classes = [IsAdminOrOwner]

    MODELS = {"buyer": Buyer, "supplier": Supplier}

    def post(self, request, kind, pk, action_name):
        model = self.MODELS.get(kind)
        if model is None:
            return Response({"detail": "kind must be 'buyer' or 'supplier'."}, status=status.HTTP_404_NOT_FOUND)
        profile = model.objects.filter(pk=pk).first()
        if profile is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if action_name == "approve":
            profile.verification_status = "approved"
            profile.rejection_reason = None
        elif action_name == "reject":
            profile.verification_status = "rejected"
            profile.rejection_reason = request.data.get("reason") or None
        else:
            return Response({"detail": "action must be approve or reject."}, status=status.HTTP_400_BAD_REQUEST)
        profile.verified_by = request.user
        profile.verified_at = timezone.now()
        if profile.user:
            if action_name == "approve":
                # Respect a deliberate profile deactivation: never re-enable login
                # for a profile whose own is_active flag is off.
                profile.user.is_active = profile.is_active
            else:
                profile.user.is_active = False
            profile.user.save(update_fields=["is_active"])
        profile.save()
        return Response({"id": profile.pk, "verification_status": profile.verification_status})


class ChangePasswordView(APIView):
    """POST /api/v2/auth/change-password/ for approved portal accounts."""

    permission_classes = [IsVerifiedPortalUser]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        log_activity(user, "update", "User", user.pk, user.username, "Changed portal password")
        return Response({"detail": "Password updated."})


class PortalNotificationListView(ListAPIView):
    """The requesting portal user's own notifications."""

    permission_classes = [IsVerifiedPortalUser]
    serializer_class = PortalNotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class PortalNotificationReadView(APIView):
    permission_classes = [IsVerifiedPortalUser]

    def post(self, request, pk):
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if notification is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(PortalNotificationSerializer(notification).data)
