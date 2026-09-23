from django.utils import timezone
from rest_framework import serializers

from buyers.models import Buyer
from eggs.models import EggProduction
from expenses.models import ExpenseRecord
from feeding.models import FeedingRecord
from flocks.models import FlockBatch
from inventory.models import InventoryItem
from medicine.models import MedicineRecord
from mortality.models import MortalityRecord
from notifications.models import Notification
from sales.models import SalesRecord
from suppliers.models import Supplier


class FlockBatchSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = FlockBatch
        fields = [
            "id", "batch_number", "breed", "quantity", "current_quantity", "age_days",
            "source", "date_acquired", "growing_stage", "status", "notes",
            "created_by_name", "created_at", "updated_at",
        ]


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_name = serializers.CharField(source="unit.abbreviation", read_only=True)
    supplier_name = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = [
            "id", "name", "category_name", "quantity", "unit_name", "supplier_name",
            "cost_per_unit", "date_purchased", "expiration_date", "reorder_level",
            "is_low_stock", "is_expired", "is_active", "updated_at",
        ]

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier_id else None

    def get_is_low_stock(self, obj):
        return obj.quantity is not None and obj.reorder_level is not None and obj.quantity <= obj.reorder_level

    def get_is_expired(self, obj):
        return bool(obj.expiration_date and obj.expiration_date <= timezone.localdate())


class EggProductionSerializer(serializers.ModelSerializer):
    flock_batch = serializers.CharField(source="flock.batch_number", read_only=True)

    class Meta:
        model = EggProduction
        fields = [
            "id", "flock_batch", "production_date", "good_eggs", "cracked_eggs",
            "rejected_eggs", "total_eggs", "remarks", "created_at",
        ]


class MortalityRecordSerializer(serializers.ModelSerializer):
    flock_batch = serializers.CharField(source="flock.batch_number", read_only=True)

    class Meta:
        model = MortalityRecord
        fields = [
            "id", "flock_batch", "date_recorded", "quantity", "cause_of_death",
            "symptoms", "action_taken", "remarks", "created_at",
        ]


class FeedingRecordSerializer(serializers.ModelSerializer):
    flock_batch = serializers.CharField(source="flock.batch_number", read_only=True)
    feed_item_name = serializers.CharField(source="feed_item.name", read_only=True)

    class Meta:
        model = FeedingRecord
        fields = [
            "id", "flock_batch", "feed_item_name", "quantity_used",
            "feeding_date", "feeding_time", "remarks", "created_at",
        ]


class MedicineRecordSerializer(serializers.ModelSerializer):
    flock_batch = serializers.CharField(source="flock.batch_number", read_only=True)
    medicine_item_name = serializers.CharField(source="medicine_item.name", read_only=True)

    class Meta:
        model = MedicineRecord
        fields = [
            "id", "flock_batch", "medicine_item_name", "medicine_type", "medicine_name",
            "dosage", "quantity_used", "date_administered", "administration_route",
            "next_schedule", "remarks", "created_at",
        ]


class SalesRecordSerializer(serializers.ModelSerializer):
    flock_batch = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesRecord
        fields = [
            "id", "product_type", "flock_batch", "buyer_name", "product_name", "quantity",
            "unit_price", "total_amount", "date_sold", "payment_status", "amount_paid",
            "notes", "created_at",
        ]

    def get_flock_batch(self, obj):
        return obj.flock.batch_number if obj.flock_id else None

    def get_buyer_name(self, obj):
        return obj.buyer.name if obj.buyer_id else None


class ExpenseRecordSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ExpenseRecord
        fields = [
            "id", "category_name", "description", "amount", "expense_date",
            "payment_method", "notes", "created_at",
        ]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id", "name", "contact_person", "phone", "email", "address",
            "supplies", "is_active", "created_at",
        ]


class BuyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buyer
        fields = [
            "id", "name", "contact_person", "phone", "email", "address",
            "buyer_type", "is_active", "created_at",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "notification_type", "title", "message", "is_read", "link", "created_at",
        ]
