from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from buyers.models import Buyer, OrderRequest
from notifications.models import ActivityLog
from sales.models import SalesRecord

User = get_user_model()


def make_user(username, role, password="pass12345"):
    return User.objects.create_user(username=username, password=password, role=role)


def sales_form_data(**overrides):
    data = {
        "product_type": "eggs",
        "product_name": "Large eggs",
        "quantity": "10",
        "unit_price": "8.00",
        "date_sold": "2026-09-20",
        "payment_status": "paid",
        "amount_paid": "80.00",
        "notes": "",
    }
    data.update(overrides)
    return data


class SalesCustodyTests(TestCase):
    """PR-1/PR-5: staff may record sales but only owner/admin may correct or delete."""

    def setUp(self):
        self.staff = make_user("staff1", "staff")
        self.owner = make_user("owner1", "owner")
        self.admin = make_user("admin1", "admin")
        self.record = SalesRecord.objects.create(
            recorded_by=self.staff, product_type="eggs", product_name="Large eggs",
            quantity=Decimal("10"), unit_price=Decimal("8.00"),
            date_sold=timezone.localdate(), payment_status="paid", amount_paid=Decimal("80"),
        )

    def test_staff_cannot_open_sale_edit_form(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("sales:sales_update", args=[self.record.pk]))
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_delete_sale(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("sales:sales_delete", args=[self.record.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SalesRecord.objects.filter(pk=self.record.pk).exists())

    def test_owner_can_edit_and_delete(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("sales:sales_update", args=[self.record.pk])).status_code, 200
        )
        response = self.client.post(reverse("sales:sales_delete", args=[self.record.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SalesRecord.objects.filter(pk=self.record.pk).exists())

    def test_owner_correction_is_logged_with_diff(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("sales:sales_update", args=[self.record.pk]),
            sales_form_data(unit_price="9.00", amount_paid="90.00"),
        )
        log = ActivityLog.objects.filter(model_name="SalesRecord", action="update").latest("created_at")
        self.assertIn("₱80.00", log.description)
        self.assertIn("₱90.00", log.description)


class BuyerCreditLimitTests(TestCase):
    def setUp(self):
        self.staff = make_user("staff1", "staff")
        self.owner = make_user("owner1", "owner")
        self.buyer = Buyer.objects.create(
            name="Limitless Ltd", credit_limit=Decimal("100.00")
        )

    def test_staff_blocked_when_credit_exceeded(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:sales_create"),
            sales_form_data(buyer=self.buyer.pk, quantity="20", unit_price="8.00",
                            amount_paid="0.00", payment_status="pending"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SalesRecord.objects.filter(buyer=self.buyer).exists())

    def test_owner_override_allowed_and_logged(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("sales:sales_create"),
            sales_form_data(buyer=self.buyer.pk, quantity="20", unit_price="8.00",
                            amount_paid="0.00", payment_status="pending"),
        )
        self.assertTrue(SalesRecord.objects.filter(buyer=self.buyer).exists())
        self.assertTrue(
            ActivityLog.objects.filter(description__icontains="Credit limit override").exists()
        )

    def test_paid_sale_needs_no_credit_headroom(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse("sales:sales_create"),
            sales_form_data(buyer=self.buyer.pk, quantity="20", unit_price="8.00",
                            amount_paid="160.00", payment_status="paid"),
        )
        self.assertTrue(SalesRecord.objects.filter(buyer=self.buyer).exists())


class QuoteStalenessTests(TestCase):
    def setUp(self):
        self.buyer_user = make_user("buyer1", "buyer")
        self.buyer = Buyer.objects.create(
            name="Ramon", user=self.buyer_user, verification_status="approved"
        )
        self.order = OrderRequest.objects.create(
            buyer=self.buyer, product_type="eggs", product_name="Eggs",
            quantity=Decimal("5"), requested_date=timezone.localdate(),
            status="quoted", quoted_unit_price=Decimal("9.00"),
        )

    def _make_stale(self):
        OrderRequest.objects.filter(pk=self.order.pk).update(
            updated_at=timezone.now() - timedelta(days=30)
        )
        self.order.refresh_from_db()

    def test_fresh_quote_is_acceptable(self):
        self.assertTrue(self.order.can_accept())

    def test_stale_quote_blocks_acceptance(self):
        self._make_stale()
        self.assertFalse(self.order.can_accept())
        self.assertTrue(self.order.is_stale)

    def test_buyer_portal_cannot_accept_stale_quote(self):
        self._make_stale()
        self.client.force_login(self.buyer_user)
        response = self.client.post(
            reverse("portal:buyer_request_respond", args=[self.order.pk]), {"action": "accept"}
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "quoted")

    def test_staff_requote_resets_staleness(self):
        self._make_stale()
        self.client.force_login(make_user("staff2", "staff"))
        response = self.client.post(
            reverse("sales:order_request_review", args=[self.order.pk]),
            {"action": "requote", "quoted_unit_price": "9.50", "staff_note": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "quoted")
        self.assertFalse(self.order.is_stale)
        self.assertTrue(self.order.can_accept())


class OnBehalfAndConvertTests(TestCase):
    def setUp(self):
        self.staff = make_user("staff1", "staff")
        self.owner = make_user("owner1", "owner")
        self.buyer = Buyer.objects.create(name="Walk-in Wilma")

    def _make_accepted(self, price="8.00"):
        return OrderRequest.objects.create(
            buyer=self.buyer, source="staff", product_type="eggs", product_name="Eggs",
            quantity=Decimal("10"), requested_date=timezone.localdate(),
            status="accepted", quoted_unit_price=Decimal(price),
        )

    def test_on_behalf_request_enters_funnel_at_accepted(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_create_internal"),
            {
                "buyer": self.buyer.pk, "product_type": "eggs", "product_name": "Tray eggs",
                "quantity": "5", "requested_unit_price": "9.00",
                "requested_date": "2026-09-25", "staff_note": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = OrderRequest.objects.get(product_name="Tray eggs")
        self.assertEqual(order.source, "staff")
        self.assertEqual(order.status, "accepted")

    def test_staff_converts_accepted_request(self):
        order = self._make_accepted()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(buyer=self.buyer.pk, quantity="10", unit_price="8.00",
                            amount_paid="80.00", payment_status="paid"),
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "converted")
        self.assertIsNotNone(order.sales_record)

    def test_staff_cannot_change_locked_price(self):
        order = self._make_accepted()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(buyer=self.buyer.pk, quantity="10", unit_price="7.00",
                            amount_paid="70.00", payment_status="paid"),
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")
        self.assertFalse(SalesRecord.objects.exists())

    def test_owner_may_override_price_at_conversion(self):
        order = self._make_accepted()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(buyer=self.buyer.pk, quantity="10", unit_price="7.00",
                            amount_paid="70.00", payment_status="paid"),
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "converted")

    def test_convert_rejects_non_accepted_request(self):
        order = self._make_accepted()
        order.status = "submitted"
        order.save()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(buyer=self.buyer.pk),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SalesRecord.objects.exists())

    def test_conversion_credit_check_blocks_staff(self):
        self.buyer.credit_limit = Decimal("50.00")
        self.buyer.save()
        order = self._make_accepted()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(buyer=self.buyer.pk, quantity="10", unit_price="8.00",
                            amount_paid="0.00", payment_status="pending"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SalesRecord.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")
