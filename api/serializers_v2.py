from rest_framework import serializers

from buyers.models import Buyer, OrderRequest
from expenses.models import ExpenseRecord
from inventory.models import InventoryItem, Unit
from inventory.services import stock_target_for_notice
from notifications.models import Notification
from sales.models import SalesRecord
from suppliers.models import DeliveryNotice, Supplier, SupplyItem


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect current password.")
        return value


class PortalNotificationSerializer(serializers.ModelSerializer):
    kind = serializers.CharField(source="notification_type", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "message", "link", "target", "is_read", "created_at"]


class ProfileEmailSyncMixin:
    """Keep the linked portal User's email in step with the profile's email.

    Without this, self-edited profile emails never reach User.email, which the
    deferred password-reset/notification flows will rely on.
    """

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        user = getattr(instance, "user", None)
        if user is not None and (user.email or "") != (instance.email or ""):
            user.email = instance.email or ""
            user.save(update_fields=["email"])
        return instance


class BuyerPortalProfileSerializer(ProfileEmailSyncMixin, serializers.ModelSerializer):
    verification_status = serializers.CharField(read_only=True)
    outstanding_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Buyer
        fields = [
            "name", "contact_person", "phone", "email", "address", "buyer_type",
            "verification_status", "credit_limit", "outstanding_balance",
        ]
        read_only_fields = ["verification_status", "credit_limit", "outstanding_balance"]
        extra_kwargs = {
            "contact_person": {"required": False, "allow_null": True},
            "phone": {"required": False, "allow_null": True},
            "email": {"required": False, "allow_null": True},
            "address": {"required": False, "allow_null": True},
        }


class SupplierPortalProfileSerializer(ProfileEmailSyncMixin, serializers.ModelSerializer):
    verification_status = serializers.CharField(read_only=True)
    payment_terms_display = serializers.CharField(source="get_payment_terms_display", read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "name", "contact_person", "phone", "email", "address", "supplies",
            "verification_status", "payment_terms", "payment_terms_display",
        ]
        read_only_fields = ["verification_status"]
        extra_kwargs = {
            "contact_person": {"required": False, "allow_null": True},
            "phone": {"required": False, "allow_null": True},
            "email": {"required": False, "allow_null": True},
            "address": {"required": False, "allow_null": True},
            "supplies": {"required": False, "allow_null": True},
        }


class OrderRequestPortalSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    quoted_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True
    )
    staff_note = serializers.CharField(read_only=True, allow_null=True)
    request_number = serializers.CharField(read_only=True)
    buyer_name = serializers.CharField(source="buyer.name", read_only=True)

    class Meta:
        model = OrderRequest
        fields = [
            "id", "request_number", "buyer_name", "source", "product_type", "product_name",
            "quantity", "requested_unit_price", "requested_date", "status",
            "quoted_unit_price", "staff_note", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "request_number", "buyer_name", "status", "created_at"]


class SalesHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesRecord
        fields = [
            "id", "product_type", "product_name", "quantity", "unit_price",
            "total_amount", "date_sold", "payment_status", "amount_paid",
        ]


class SupplyItemSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True, default=None)

    class Meta:
        model = SupplyItem
        fields = [
            "id", "supplier_name", "name", "category", "unit_price", "unit",
            "unit_name", "availability", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "supplier_name", "created_at"]
        extra_kwargs = {
            "category": {"required": False, "allow_null": True},
            "unit_price": {"required": False, "allow_null": True},
            "unit": {"required": False, "allow_null": True},
        }


class SupplyUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "abbreviation"]


class DeliveryNoticePortalSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    origin = serializers.CharField(read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = DeliveryNotice
        fields = [
            "id", "supplier_name", "origin", "supply_item", "description", "quantity",
            "expected_date", "supplier_note", "status", "created_at",
        ]
        read_only_fields = ["id", "supplier_name", "origin", "status", "created_at"]

    def validate_supply_item(self, value):
        request = self.context["request"]
        if value is not None and value.supplier_id != request.user.supplier.pk:
            raise serializers.ValidationError("Unknown supply item.")
        return value


class PurchaseHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseRecord
        fields = ["id", "description", "amount", "expense_date", "payment_method"]


class FarmOrderResponseSerializer(serializers.ModelSerializer):
    """Supplier confirms or adjusts a farm-ordered delivery."""

    class Meta:
        model = DeliveryNotice
        fields = ["expected_date", "supplier_note"]
        extra_kwargs = {
            "expected_date": {"required": False},
            "supplier_note": {"required": False, "allow_blank": True},
        }


class OrderRequestStaffSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source="buyer.name", read_only=True)
    timeline_status = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OrderRequest
        fields = [
            "id", "request_number", "buyer", "buyer_name", "source", "product_type",
            "product_name", "quantity", "requested_unit_price", "requested_date",
            "status", "timeline_status", "quoted_unit_price", "staff_note",
            "sales_record", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "request_number", "sales_record", "created_at"]


class QuoteActionSerializer(serializers.Serializer):
    quoted_unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    staff_note = serializers.CharField(required=False, allow_blank=True)


class RejectActionSerializer(serializers.Serializer):
    staff_note = serializers.CharField(required=False, allow_blank=True)


class ConvertSaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesRecord
        fields = [
            "product_type", "flock", "buyer", "product_name", "quantity",
            "unit_price", "date_sold", "payment_status", "amount_paid", "notes",
        ]
        extra_kwargs = {
            "flock": {"required": False, "allow_null": True},
            "buyer": {"required": False},
            "amount_paid": {"required": False},
            "notes": {"required": False, "allow_blank": True},
        }


class DeliveryNoticeStaffSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    # Lets clients prefill the booked amount as the web review page does (unit price x quantity).
    supply_item_price = serializers.DecimalField(
        source="supply_item.unit_price", max_digits=10, decimal_places=2, read_only=True, allow_null=True
    )
    # The stock row a receive would land in if left untouched (explicit booking, else catalog
    # mapping), so the mobile picker can preselect it. Null means no booking will happen.
    mapped_inventory_item = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryNotice
        fields = [
            "id", "supplier", "supplier_name", "origin", "supply_item", "supply_item_price", "description",
            "quantity", "expected_date", "supplier_note", "status", "expense_record", "inventory_item",
            "mapped_inventory_item", "created_at",
        ]
        read_only_fields = ["id", "supplier_name", "origin", "expense_record", "inventory_item", "created_at"]

    def get_mapped_inventory_item(self, obj):
        target = stock_target_for_notice(obj)
        return target.pk if target else None


class FarmOrderCreateSerializer(serializers.ModelSerializer):
    """Payload for a farm-initiated purchase order; mirrors FarmDeliveryOrderForm."""

    class Meta:
        model = DeliveryNotice
        fields = ["supplier", "supply_item", "description", "quantity", "expected_date"]

    def validate_supplier(self, value):
        if not value.is_active or value.verification_status != "approved":
            raise serializers.ValidationError("Only an approved supplier can receive farm orders.")
        return value

    def validate_supply_item(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This catalog item is no longer offered.")
        return value

    def validate(self, attrs):
        item = attrs.get("supply_item")
        if item and item.supplier_id != attrs["supplier"].pk:
            raise serializers.ValidationError({"supply_item": "This item is not in the selected supplier's catalog."})
        return attrs


class ReceiveExpenseSerializer(serializers.ModelSerializer):
    # Receive-time stock decision; consumed by the view, never saved on ExpenseRecord.
    inventory_item = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItem.objects.filter(is_active=True), required=False, allow_null=True,
    )

    class Meta:
        model = ExpenseRecord
        fields = ["category", "description", "amount", "expense_date", "payment_method", "notes", "inventory_item"]
        extra_kwargs = {
            "notes": {"required": False, "allow_blank": True},
        }
