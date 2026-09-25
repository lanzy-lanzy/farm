from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import FlockBatch

User = get_user_model()


class FlockModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.flock = FlockBatch.objects.create(
            batch_number="B001",
            breed="Rhode Island Red",
            quantity=100,
            date_acquired="2024-01-01",
            created_by=self.user,
        )

    def test_flock_creation(self):
        self.assertEqual(FlockBatch.objects.count(), 1)
        self.assertEqual(self.flock.batch_number, "B001")

    def test_default_current_quantity(self):
        self.assertEqual(self.flock.current_quantity, 100)

    def test_default_status(self):
        self.assertEqual(self.flock.status, "active")

    def test_str_representation(self):
        self.assertEqual(str(self.flock), "B001 - Rhode Island Red")

    def test_remaining_stock(self):
        self.assertEqual(self.flock.remaining_stock(), 100)

    def test_death_count_zero(self):
        self.assertEqual(self.flock.death_count(), 0)


class FlockViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.client.force_login(self.user)
        FlockBatch.objects.create(
            batch_number="B001",
            breed="Rhode Island Red",
            quantity=100,
            date_acquired="2024-01-01",
            created_by=self.user,
        )

    def test_flock_list_view(self):
        response = self.client.get(reverse("flocks:flock_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B001")

    def test_flock_create_view(self):
        form_data = {
            "batch_number": "B002",
            "breed": "Leghorn",
            "quantity": 200,
            "age_days": 0,
            "date_acquired": "2024-02-01",
            "growing_stage": "chick",
            "status": "active",
        }
        response = self.client.post(reverse("flocks:flock_create"), form_data)
        self.assertRedirects(response, reverse("flocks:flock_list"))
        self.assertEqual(FlockBatch.objects.count(), 2)