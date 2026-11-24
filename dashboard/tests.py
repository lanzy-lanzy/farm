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
        self.assertContains(response, "Print Graph")
        self.assertContains(response, "printDashboardChart")
        # Peso icon in admin sidebar, no legacy dollar icon
        self.assertContains(response, "M9.5 16.5V7.5")
        self.assertNotContains(response, "M12 8c-1.657")


class ManagerStaffRBACTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="manager_staff",
            password="password123",
            role="staff",
        )
        self.client.force_login(self.staff)

    def test_staff_dashboard_only_shows_farm_operations_cards_and_printable_chart(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        # Farm operations cards & chart are visible
        self.assertContains(response, "Total Chickens")
        self.assertContains(response, "Active Flocks")
        self.assertContains(response, "Today's Eggs")
        self.assertContains(response, "Mortality (30 days)")
        self.assertContains(response, "Egg Production (Last 7 Days)")
        self.assertContains(response, "eggProductionChart")
        self.assertContains(response, "Print Graph")
        # Non-farm-operations cards & chart are hidden
        self.assertNotContains(response, "Low Stock Items")
        self.assertNotContains(response, "Receivables (unpaid sales)")
        self.assertNotContains(response, "Open order requests")
        self.assertNotContains(response, "Announced deliveries")
        self.assertNotContains(response, "Sales Summary")
        self.assertNotContains(response, "Expenses Summary")
        self.assertNotContains(response, "Egg Trays Sold (Last 7 Days)")

    def test_staff_sidebar_only_shows_farm_operations_and_reports(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        for url_name in (
            "flocks:flock_list",
            "feeding:feeding_list",
            "eggs:egg_list",
            "deaths:death_list",
            "medicine:medicine_list",
            "reports:reports_index",
        ):
            self.assertContains(response, reverse(url_name))
        for forbidden_url_name in (
            "sales:sales_list",
            "sales:order_request_queue",
            "sales:product_list",
            "buyers:buyer_list",
            "inventory:inventory_list",
            "expenses:expense_list",
            "expenses:delivery_notice_queue",
            "suppliers:supplier_list",
            "accounts:user_list",
            "settings_app:settings",
        ):
            self.assertNotContains(response, reverse(forbidden_url_name))

    def test_staff_can_access_farm_operations_views_and_is_blocked_from_others(self):
        for allowed in (
            "flocks:flock_list",
            "feeding:feeding_list",
            "eggs:egg_list",
            "deaths:death_list",
            "medicine:medicine_list",
        ):
            with self.subTest(allowed=allowed):
                self.assertEqual(self.client.get(reverse(allowed)).status_code, 200)

        for forbidden in (
            "sales:sales_list",
            "sales:order_request_queue",
            "sales:product_list",
            "buyers:buyer_list",
            "inventory:inventory_list",
            "expenses:expense_list",
            "expenses:delivery_notice_queue",
            "suppliers:supplier_list",
            "settings_app:settings",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(self.client.get(reverse(forbidden)).status_code, 403)
