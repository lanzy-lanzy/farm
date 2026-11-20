from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from sales.models import SalesRecord

User = get_user_model()


class DashboardTraysSoldChartTests(TestCase):
    def setUp(self):
        SalesRecord.objects.all().delete()
        self.admin = User.objects.create_user(
            username="admin_test",
            password="password123",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin)

    def test_dashboard_bar_chart_counts_egg_trays_sold_last_7_days(self):
        today = timezone.now().date()
        SalesRecord.objects.create(
            product_type="eggs",
            product_name="Eggs (tray)",
            quantity=Decimal("10.00"),
            unit_price=Decimal("560.00"),
            date_sold=today,
            recorded_by=self.admin,
        )
        SalesRecord.objects.create(
            product_type="eggs",
            product_name="Tray eggs (walk-in)",
            quantity=Decimal("5.00"),
            unit_price=Decimal("560.00"),
            date_sold=today,
            recorded_by=self.admin,
        )
        SalesRecord.objects.create(
            product_type="eggs",
            product_name="Eggs (tray)",
            quantity=Decimal("8.00"),
            unit_price=Decimal("560.00"),
            date_sold=today - timedelta(days=3),
            recorded_by=self.admin,
        )
        # Non-egg sale on today should not be counted
        SalesRecord.objects.create(
            product_type="chicken",
            product_name="Live Chicken",
            quantity=Decimal("12.00"),
            unit_price=Decimal("250.00"),
            date_sold=today,
            recorded_by=self.admin,
        )
        # Older egg sale outside the 7-day window should not be counted
        SalesRecord.objects.create(
            product_type="eggs",
            product_name="Eggs (tray)",
            quantity=Decimal("50.00"),
            unit_price=Decimal("560.00"),
            date_sold=today - timedelta(days=10),
            recorded_by=self.admin,
        )

        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)

        chart_data = response.context["trays_sold_chart_data"]
        self.assertEqual(len(chart_data), 7)
        self.assertEqual(chart_data[-1]["trays"], 15)
        self.assertEqual(chart_data[-4]["trays"], 8)
        self.assertEqual(response.context["total_trays_sold_7d"], 23)

        self.assertContains(response, "Egg Trays Sold (Last 7 Days)")
        self.assertContains(response, "type: 'bar'")
        self.assertContains(response, "traysSoldChart")
        self.assertContains(response, "Total: 23 trays")
