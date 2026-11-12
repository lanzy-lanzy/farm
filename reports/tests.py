import io
from decimal import Decimal

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from deaths.models import DeathRecord
from flocks.models import FlockBatch
from sales.models import SalesRecord

User = get_user_model()

PDF_EXPORT_URLS = [
    "reports:export_production_pdf",
    "reports:export_death_pdf",
    "reports:export_sales_pdf",
    "reports:export_expense_pdf",
    "reports:export_inventory_pdf",
    "reports:export_profit_loss_pdf",
]

EXCEL_EXPORT_URLS = [
    "reports:export_production_excel",
    "reports:export_death_excel",
    "reports:export_sales_excel",
    "reports:export_expense_excel",
    "reports:export_inventory_excel",
    "reports:export_profit_loss_excel",
]

PRINT_VIEW_URLS = [
    "reports:production_report_print",
    "reports:death_report_print",
    "reports:sales_report_print",
    "reports:expense_report_print",
    "reports:inventory_report_print",
    "reports:profit_loss_report_print",
]


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


class ReportDataTests(TestCase):
    """A flock plus one sale and one death, inside the default rolling window."""

    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.client.force_login(self.user)
        self.today = timezone.now().date()
        self.flock = FlockBatch.objects.create(
            batch_number="T-TEST-01",
            breed="Layer",
            quantity=100,
            date_acquired=self.today,
        )
        self.sale = SalesRecord.objects.create(
            product_name="Egg Tray Large",
            quantity=Decimal("5"),
            unit_price=Decimal("120.00"),
            date_sold=self.today,
        )
        self.death = DeathRecord.objects.create(
            flock=self.flock,
            date_recorded=self.today,
            quantity=3,
            cause_of_death="Heat stress",
        )


class PdfExportTests(ReportDataTests):
    def test_every_pdf_endpoint_returns_a_downloadable_pdf(self):
        for name in PDF_EXPORT_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertIn("attachment", response["Content-Disposition"])
                self.assertTrue(response.content.startswith(b"%PDF"))
                self.assertGreater(len(response.content), 1000)

    def test_pdf_filename_records_the_requested_period(self):
        url = reverse("reports:export_sales_pdf") + "?start_date=2026-01-01&end_date=2026-01-31"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("2026-01-31", response["Content-Disposition"])

    def test_pdf_export_is_internal_only(self):
        outsider = User.objects.create_user(username="vendor", password="pw", role="buyer")
        self.client.force_login(outsider)
        for name in PDF_EXPORT_URLS:
            with self.subTest(url=name):
                self.assertIn(self.client.get(reverse(name)).status_code, (302, 403))


class ExcelExportTests(ReportDataTests):
    def test_every_excel_endpoint_returns_a_workbook(self):
        for name in EXCEL_EXPORT_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "spreadsheetml.sheet", response["Content-Type"]
                )

    def test_excel_exports_include_the_saved_rows(self):
        expected = {
            "reports:export_sales_excel": "Egg Tray Large",
            "reports:export_death_excel": "Heat stress",
        }
        for name, needle in expected.items():
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
                values = {cell.value for row in sheet.iter_rows() for cell in row}
                self.assertIn(needle, values)


class PrintPreviewTests(ReportDataTests):
    def test_print_preview_offers_print_and_a_separate_pdf_download(self):
        for name in PRINT_VIEW_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "window.print()")
                self.assertContains(response, "/export-pdf/")

    def test_print_preview_renders_saved_record_fields(self):
        self.assertContains(
            self.client.get(reverse("reports:sales_report_print")), "Egg Tray Large"
        )
        self.assertContains(
            self.client.get(reverse("reports:death_report_print")), "Heat stress"
        )

    def test_print_preview_uses_the_peso_sign(self):
        response = self.client.get(reverse("reports:sales_report_print"))
        self.assertContains(response, "\u20b1")
        self.assertNotContains(response, "$")


class ReportsHubTests(ReportDataTests):
    def test_hub_offers_all_four_destinations_per_report(self):
        response = self.client.get(reverse("reports:reports_index"))
        self.assertEqual(response.status_code, 200)
        for name in PDF_EXPORT_URLS:
            self.assertContains(response, reverse(name))
        for name in EXCEL_EXPORT_URLS:
            self.assertContains(response, reverse(name))
        for name in PRINT_VIEW_URLS:
            self.assertContains(response, reverse(name))

    def test_hub_has_no_combined_print_or_pdf_action(self):
        response = self.client.get(reverse("reports:reports_index"))
        self.assertNotContains(response, "Print / PDF")


class BrandingTests(ReportDataTests):
    """The farm badge is the default branding on every report output."""

    def test_print_preview_uses_the_bundled_badge(self):
        response = self.client.get(reverse("reports:production_report_print"))
        self.assertContains(response, "/static/images/farm-logo.png")

    def test_pdf_letterhead_embeds_the_farm_badge(self):
        response = self.client.get(reverse("reports:export_production_pdf"))
        self.assertIn(b"/Subtype /Image", response.content)
