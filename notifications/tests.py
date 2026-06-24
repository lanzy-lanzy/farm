from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Notification, ActivityLog

User = get_user_model()


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.notification = Notification.objects.create(
            user=self.user,
            notification_type="low_stock",
            title="Low Stock Alert",
            message="Item is running low",
        )

    def test_notification_creation(self):
        self.assertEqual(Notification.objects.count(), 1)

    def test_default_is_read(self):
        self.assertFalse(self.notification.is_read)

    def test_mark_as_read(self):
        self.notification.mark_as_read()
        self.assertTrue(self.notification.is_read)

    def test_str_representation(self):
        self.assertEqual(str(self.notification), "Low Stock Alert - admin")


class ActivityLogModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.log = ActivityLog.objects.create(
            user=self.user,
            action="create",
            model_name="FlockBatch",
            object_repr="B001",
        )

    def test_activity_log_creation(self):
        self.assertEqual(ActivityLog.objects.count(), 1)

    def test_str_representation(self):
        self.assertIn("Created", str(self.log))
        self.assertIn("Created", str(self.log))


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.client.force_login(self.user)
        Notification.objects.create(
            user=self.user,
            notification_type="activity",
            title="Test Notification",
            message="Test message",
        )

    def test_notification_list_view(self):
        response = self.client.get(reverse("notifications:notification_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Notification")

    def test_mark_as_read_view(self):
        notification = Notification.objects.first()
        response = self.client.get(
            reverse("notifications:notification_mark_read", args=[notification.pk])
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_activity_log_view(self):
        ActivityLog.objects.create(
            user=self.user,
            action="create",
            model_name="Test",
            object_repr="TestObj",
        )
        response = self.client.get(reverse("notifications:activity_log"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TestObj")

