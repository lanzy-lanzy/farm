from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from buyers.models import Buyer, OrderRequest
from suppliers.models import Supplier, SupplyItem

User = get_user_model()


class ApiV2PortalTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="staff1", password="x", role="staff")
        self.owner = User.objects.create_user(username="own", password="x", role="owner")
        buyer_user = User.objects.create_user(username="b1", password="x", role="buyer")
        self.buyer = Buyer.objects.create(name="API Buyer", user=buyer_user, verification_status="approved")
        self.buyer_user = buyer_user
        supplier_user = User.objects.create_user(username="s1", password="x", role="supplier")
        self.supplier = Supplier.objects.create(name="API Supplier", user=supplier_user, verification_status="approved")
        self.supplier_user = supplier_user

    def token(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return token.key

    def as_user(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token(user)}")

    def test_buyer_can_create_and_own_order_request(self):
        self.as_user(self.buyer_user)
        response = self.client.post(reverse("portal-order-requests-list"), {
            "product_type": "eggs", "product_name": "Ballut eggs", "quantity": "30",
            "requested_date": "2026-09-28",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        order_id = response.json()["id"]
        list_response = self.client.get(reverse("portal-order-requests-list"))
        self.assertEqual(len(list_response.json()["results"]), 1)
        # staff sees nothing through the portal endpoint
        self.as_user(self.staff)
        forbidden = self.client.get(reverse("portal-order-requests-list"))
        self.assertEqual(forbidden.status_code, 403)

    def test_staff_quote_convert_and_buyer_accept_cycle(self):
        order = OrderRequest.objects.create(buyer=self.buyer, product_type="eggs", product_name="Eggs", quantity=10, requested_date="2026-09-28")
        self.as_user(self.staff)
        quote = self.client.post(
            reverse("internal-order-requests-quote", args=[order.pk]),
            {"quoted_unit_price": "9.00", "staff_note": "ok"}, format="json",
        )
        self.assertEqual(quote.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "quoted")
        # buyer accepts through API
        self.as_user(self.buyer_user)
        accept = self.client.post(reverse("portal-order-requests-accept", args=[order.pk]), {}, format="json")
        self.assertEqual(accept.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")
        # staff converts through API
        from expenses.models import ExpenseCategory
        self.as_user(self.staff)
        convert = self.client.post(
            reverse("internal-order-requests-convert", args=[order.pk]),
            {"product_type": "eggs", "product_name": "Eggs", "quantity": "10",
             "unit_price": "9.00", "date_sold": "2026-09-28", "payment_status": "paid",
             "amount_paid": "90"}, format="json",
        )
        self.assertEqual(convert.status_code, 201, convert.content)
        order.refresh_from_db()
        self.assertEqual(order.status, "converted")
        self.assertIsNotNone(order.sales_record_id)

    def test_supplier_catalog_and_notice(self):
        self.as_user(self.supplier_user)
        create = self.client.post(reverse("portal-supply-items-list"), {
            "name": "Vaccine flu", "unit_price": "25", "availability": "in_stock",
        }, format="json")
        self.assertEqual(create.status_code, 201)
        item_id = create.json()["id"]
        notice = self.client.post(reverse("portal-delivery-notices-list"), {
            "supply_item": item_id, "description": "cold chain box", "quantity": "5",
            "expected_date": "2026-09-29",
        }, format="json")
        self.assertEqual(notice.status_code, 201)
        # buyer cannot create supply items
        self.as_user(self.buyer_user)
        rejected = self.client.post(reverse("portal-supply-items-list"), {
            "name": "hax", "availability": "in_stock",
        }, format="json")
        self.assertEqual(rejected.status_code, 403)

    def test_verification_endpoints_admin_gated_for_staff(self):
        user = User.objects.create_user(username="s2", password="x", role="supplier")
        pending = Supplier.objects.create(name="Pending Supplies", user=user, verification_status="pending")
        self.as_user(self.owner)
        pending_list = self.client.get(reverse("api-v2-verifications-pending"))
        self.assertEqual(pending_list.status_code, 200)
        approve = self.client.post(reverse("api-v2-verification-action", args=["supplier", pending.pk, "approve"]), {}, format="json")
        self.assertEqual(approve.status_code, 200)
        pending.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(pending.verification_status, "approved")
        self.assertTrue(user.is_active)

    def test_read_only_v1_still_owner_scoped(self):
        self.as_user(self.buyer_user)
        response = self.client.get("/api/buyers/")
        self.assertEqual(response.status_code, 403)
