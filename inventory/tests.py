from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import InventoryItem, InventoryCategory, Unit, InventoryTransaction

User = get_user_model()


class InventoryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.category = InventoryCategory.objects.create(name="Feed")
        self.unit = Unit.objects.create(name="Kilogram", abbreviation="kg")
        self.item = InventoryItem.objects.create(
            category=self.category,
            name="Chicken Feed",
            quantity=50,
            unit=self.unit,
            reorder_level=20,
            cost_per_unit=10,
            created_by=self.user,
        )

    def test_item_creation(self):
        self.assertEqual(InventoryItem.objects.count(), 1)

    def test_low_stock(self):
        self.assertFalse(self.item.is_low_stock())
        self.item.quantity = 10
        self.assertTrue(self.item.is_low_stock())

    def test_not_expired(self):
        self.assertFalse(self.item.is_expired())

    def test_expired(self):
        self.item.expiration_date = timezone.now().date() - timezone.timedelta(days=1)
        self.assertTrue(self.item.is_expired())

    def test_str_representation(self):
        self.assertEqual(str(self.item), "Chicken Feed (50 kg)")

    def test_stock_in_transaction(self):
        InventoryTransaction.objects.create(
            item=self.item,
            transaction_type="in",
            quantity=30,
            created_by=self.user,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 80)

    def test_stock_out_transaction(self):
        InventoryTransaction.objects.create(
            item=self.item,
            transaction_type="out",
            quantity=10,
            created_by=self.user,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 40)


class InventoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.client.force_login(self.user)
        category = InventoryCategory.objects.create(name="Feed")
        unit = Unit.objects.create(name="Kilogram", abbreviation="kg")
        InventoryItem.objects.create(
            category=category,
            name="Chicken Feed",
            quantity=50,
            unit=unit,
            reorder_level=20,
            cost_per_unit=10,
            created_by=self.user,
        )

    def test_inventory_list_view(self):
        response = self.client.get(reverse("inventory:inventory_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chicken Feed")


class NotificationUtilTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.category = InventoryCategory.objects.create(name="Feed")
        self.unit = Unit.objects.create(name="Kilogram", abbreviation="kg")
        self.item = InventoryItem.objects.create(
            category=self.category,
            name="Chicken Feed",
            quantity=5,
            unit=self.unit,
            reorder_level=20,
            created_by=self.user,
        )

    def test_low_stock_notification_creation(self):
        from notifications.utils import notify_low_stock

        notify_low_stock(self.item)
        from notifications.models import Notification

        self.assertTrue(Notification.objects.filter(notification_type="low_stock").exists())