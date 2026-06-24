from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AccountsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin", password="admin123", role="admin"
        )
        self.staff_user = User.objects.create_user(
            username="staff", password="staff123", role="staff"
        )

    def test_user_creation(self):
        self.assertEqual(User.objects.count(), 2)

    def test_user_roles(self):
        self.assertEqual(self.admin_user.role, "admin")
        self.assertEqual(self.staff_user.role, "staff")

    def test_login_required(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotEqual(response.status_code, 200)

    def test_login_success(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "admin", "password": "admin123"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))

    def test_login_failure(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "admin", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid")

    def test_user_list_view(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin")
        self.assertContains(response, "staff")