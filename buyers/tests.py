from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from buyers.models import Buyer, OrderRequest
from sales.models import SalesRecord

User = get_user_model()


def make_buyer_user(**kwargs):
    role = kwargs.pop("role", "buyer")
    user = User.objects.create_user(username=kwargs.pop("username", "buyer1"), password="pass12345", role=role, **kwargs)
    return user


class BuyerPortalAccessTests(TestCase):
    def setUp(self):
        self.staff = make_buyer_user(username="staff1", role="staff")
        self.buyer_user = make_buyer_user()
        self.buyer = Buyer.objects.create(name="Ramon Eggs", phone="09123", email="r@e.ph", user=self.buyer_user, verification_status="approved")

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("portal:buyer_home"))
        self.assertEqual(response.status_code, 302)

    def test_internal_staff_blocked_from_buyer_portal(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("portal:buyer_home"))
        self.assertEqual(response.status_code, 403)

    def test_login_lands_external_user_on_portal(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "buyer1", "password": "pass12345"}
        )
        self.assertRedirects(
            response, "/portal/", fetch_redirect_response=False
        )

    def test_external_user_cannot_reach_internal_pages(self):
        self.client.force_login(self.buyer_user)
        response = self.client.get("/sales/", follow=False)
        self.assertRedirects(response, "/portal/", fetch_redirect_response=False)

    def test_other_buyers_orders_are_not_visible(self):
        other_user = make_buyer_user(username="buyer2")
        other = Buyer.objects.create(name="Other Buyer", user=other_user, verification_status="approved")
        OrderRequest.objects.create(
            buyer=other, product_type="eggs", product_name="Extra eggs",
            quantity=5, requested_date="2026-09-25",
        )
        self.client.force_login(self.buyer_user)
        response = self.client.get(reverse("portal:buyer_requests"))
        self.assertNotContains(response, "Extra eggs")


class OrderRequestFlowTests(TestCase):
    def setUp(self):
        self.staff = make_buyer_user(username="staff1", role="staff")
        self.buyer_user = make_buyer_user()
        self.buyer = Buyer.objects.create(name="Ramon Eggs", user=self.buyer_user, verification_status="approved")

    def _submit(self):
        self.client.force_login(self.buyer_user)
        response = self.client.post(reverse("portal:buyer_request_create"), {
            "product_type": "eggs", "product_name": "Large eggs", "quantity": "100",
            "requested_unit_price": "7.50", "requested_date": "2026-09-25",
        })
        self.assertEqual(response.status_code, 302)
        return OrderRequest.objects.get(buyer=self.buyer)

    def test_submit_creates_request_and_notifies_team(self):
        order = self._submit()
        self.assertEqual(order.status, "submitted")
        self.assertTrue(order.request_number.startswith("REQ-"))
        self.assertTrue(self.staff.notifications.filter(notification_type="order_request").exists())

    def test_quote_then_accept_then_convert(self):
        order = self._submit()
        # staff quotes
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_review", args=[order.pk]),
            {"action": "quote", "quoted_unit_price": "8.00", "staff_note": "Fresh stock"},
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "quoted")
        self.assertTrue(self.buyer_user.notifications.filter(title__contains="Quote").exists())
        # buyer accepts
        self.client.force_login(self.buyer_user)
        self.client.post(reverse("portal:buyer_request_respond", args=[order.pk]), {"action": "accept"})
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")
        # staff converts via sales create form
        self.client.force_login(self.staff)
        response = self.client.post(reverse("sales:sales_create"), {
            "product_type": "eggs", "buyer": self.buyer.pk, "product_name": "Large eggs",
            "quantity": "100", "unit_price": "8.00", "date_sold": "2026-09-25",
            "payment_status": "paid", "amount_paid": "800.00", "order_request": order.pk,
        })
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        record = SalesRecord.objects.get(buyer=self.buyer)
        self.assertEqual(order.status, "converted")
        self.assertEqual(order.sales_record_id, record.pk)
        self.assertTrue(self.buyer_user.notifications.filter(title__contains="recorded").exists())

    def test_accept_before_quote_is_blocked(self):
        order = self._submit()
        self.client.force_login(self.buyer_user)
        response = self.client.post(reverse("portal:buyer_request_respond", args=[order.pk]), {"action": "accept"})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "submitted")

    def test_cancel_allowed_before_accepted(self):
        order = self._submit()
        self.client.force_login(self.buyer_user)
        self.client.post(reverse("portal:buyer_request_cancel", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")

    def test_convert_requires_accepted(self):
        order = self._submit()
        self.client.force_login(self.staff)
        self.client.post(reverse("sales:sales_create"), {
            "product_type": "eggs", "buyer": self.buyer.pk, "product_name": "Large eggs",
            "quantity": "100", "unit_price": "8.00", "date_sold": "2026-09-25",
            "payment_status": "paid", "amount_paid": "800.00", "order_request": order.pk,
        })
        order.refresh_from_db()
        self.assertEqual(order.status, "submitted")
        self.assertIsNone(order.sales_record_id)


class BuyerAccountLifecycleTests(TestCase):
    def setUp(self):
        self.staff = make_buyer_user(username="staff1", role="staff")

    def test_create_account_links_user_and_preapproves(self):
        buyer = Buyer.objects.create(name="Walk-inBuyer Here", email="w@i.ph")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("buyers:buyer_create_account", args=[buyer.pk]))
        self.assertEqual(response.status_code, 302)
        buyer.refresh_from_db()
        self.assertIsNotNone(buyer.user)
        self.assertEqual(buyer.user.role, "buyer")
        self.assertEqual(buyer.verification_status, "approved")

    def test_deactivating_buyer_revokes_login(self):
        buyer_user = make_buyer_user()
        buyer = Buyer.objects.create(name="Byrd", user=buyer_user, verification_status="approved")
        buyer.is_active = False
        buyer.save()
        buyer_user.refresh_from_db()
        self.assertFalse(buyer_user.is_active)

    def test_pending_buyer_cannot_log_in(self):
        user = make_buyer_user()
        user.is_active = False
        user.save()
        self.assertFalse(self.client.login(username="buyer1", password="pass12345"))
