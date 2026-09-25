from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ReportViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.client.force_login(self.user)

    def test_reports_index_view(self):
        response = self.client.get(reverse("reports:reports_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reports")

    def test_production_report_view(self):
        response = self.client.get(reverse("reports:production_report"))
        self.assertEqual(response.status_code, 200)

    def test_death_report_view(self):
        response = self.client.get(reverse("reports:death_report"))
        self.assertEqual(response.status_code, 200)

    def test_sales_report_view(self):
        response = self.client.get(reverse("reports:sales_report"))
        self.assertEqual(response.status_code, 200)

    def test_expense_report_view(self):
        response = self.client.get(reverse("reports:expense_report"))
        self.assertEqual(response.status_code, 200)

    def test_inventory_report_view(self):
        response = self.client.get(reverse("reports:inventory_report"))
        self.assertEqual(response.status_code, 200)

    def test_profit_loss_report_view(self):
        response = self.client.get(reverse("reports:profit_loss_report"))
        self.assertEqual(response.status_code, 200)
