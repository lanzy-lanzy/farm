from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from buyers.models import Buyer, OrderRequest
from notifications.models import Notification
from suppliers.models import DeliveryNotice, Supplier, SupplyItem

User = get_user_model()


class AuthMixin:
    def token(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return token.key

    def as_user(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token(user)}")


class ApiV2PortalTests(AuthMixin, APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="staff1", password="x", role="staff")
        self.owner = User.objects.create_user(username="own", password="x", role="owner")
        buyer_user = User.objects.create_user(username="b1", password="x", role="buyer")
        self.buyer = Buyer.objects.create(name="API Buyer", user=buyer_user, verification_status="approved")
        self.buyer_user = buyer_user
        supplier_user = User.objects.create_user(username="s1", password="x", role="supplier")
        self.supplier = Supplier.objects.create(name="API Supplier", user=supplier_user, verification_status="approved")
        self.supplier_user = supplier_user

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

    def test_staff_can_requote_a_quoted_request(self):
        order = OrderRequest.objects.create(
            buyer=self.buyer, product_type="eggs", product_name="Eggs", quantity=10,
            requested_date="2026-09-28", status="quoted", quoted_unit_price=9,
        )
        self.as_user(self.staff)
        requote = self.client.post(
            reverse("internal-order-requests-quote", args=[order.pk]),
            {"quoted_unit_price": "8.50", "staff_note": "price update"}, format="json",
        )
        self.assertEqual(requote.status_code, 200, requote.content)
        order.refresh_from_db()
        self.assertEqual((order.status, str(order.quoted_unit_price)), ("quoted", "8.50"))
        order.status = "converted"
        order.save()
        closed = self.client.post(
            reverse("internal-order-requests-quote", args=[order.pk]),
            {"quoted_unit_price": "7.00"}, format="json",
        )
        self.assertEqual(closed.status_code, 400)

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

    def test_staff_can_place_farm_order_that_opens_the_supplier_portal(self):
        item = SupplyItem.objects.create(supplier=self.supplier, name="Layer feed 50kg", unit_price=1150)
        self.as_user(self.staff)
        response = self.client.post(reverse("internal-delivery-notices-list"), {
            "supplier": self.supplier.pk, "supply_item": item.pk, "description": "corn feed",
            "quantity": "5", "expected_date": "2026-10-01",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["origin"], "farm")
        notice = DeliveryNotice.objects.get(pk=response.json()["id"])
        self.assertEqual((notice.status, notice.created_by), ("announced", self.staff))
        ping = Notification.objects.get(user=self.supplier_user, notification_type="delivery_notice")
        self.assertEqual(ping.target, f"delivery_notice:{notice.pk}")
        self.assertIn("The farm ordered", ping.title)

    def test_farm_order_confirm_then_receive_cycle(self):
        from expenses.models import ExpenseCategory
        item = SupplyItem.objects.create(supplier=self.supplier, name="Corn feed 50kg", unit_price=100)
        self.as_user(self.staff)
        created = self.client.post(reverse("internal-delivery-notices-list"), {
            "supplier": self.supplier.pk, "supply_item": item.pk, "description": "grower mash",
            "quantity": "10", "expected_date": "2026-10-01",
        }, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        notice_id = created.json()["id"]

        self.as_user(self.supplier_user)
        confirmed = self.client.post(reverse("portal-delivery-notices-respond", args=[notice_id]), {
            "expected_date": "2026-10-05", "supplier_note": "by truck",
        }, format="json")
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        notice = DeliveryNotice.objects.get(pk=notice_id)
        self.assertFalse(notice.is_farm_order_open)
        self.assertTrue(notice.can_supplier_respond)

        adjusted = self.client.post(reverse("portal-delivery-notices-respond", args=[notice_id]), {
            "expected_date": "2026-10-06",
        }, format="json")
        self.assertEqual(adjusted.status_code, 200, adjusted.content)
        self.assertEqual(str(adjusted.json()["expected_date"]), "2026-10-06")

        self.as_user(self.staff)
        received = self.client.post(reverse("internal-delivery-notices-receive", args=[notice_id]), {
            "category": ExpenseCategory.objects.create(name="Feed").pk, "description": "grower mash",
            "amount": "1000", "expense_date": "2026-10-06", "payment_method": "cash",
        }, format="json")
        self.assertEqual(received.status_code, 201, received.content)
        self.assertEqual(received.json()["status"], "received")
        notice.refresh_from_db()
        self.assertFalse(notice.can_supplier_respond)

    def test_farm_order_validation_and_role_gating(self):
        other_user = User.objects.create_user(username="s9", password="x", role="supplier")
        other = Supplier.objects.create(name="Other Supplies", user=other_user, verification_status="approved")
        foreign_item = SupplyItem.objects.create(supplier=other, name="Foreign item", unit_price=10)
        pending_user = User.objects.create_user(username="s10", password="x", role="supplier")
        pending = Supplier.objects.create(name="Pending Supplies", user=pending_user, verification_status="pending")

        self.as_user(self.staff)
        mismatch = self.client.post(reverse("internal-delivery-notices-list"), {
            "supplier": self.supplier.pk, "supply_item": foreign_item.pk, "quantity": "1",
            "expected_date": "2026-10-01",
        }, format="json")
        self.assertEqual(mismatch.status_code, 400, mismatch.content)
        unapproved = self.client.post(reverse("internal-delivery-notices-list"), {
            "supplier": pending.pk, "description": "hax", "quantity": "1", "expected_date": "2026-10-01",
        }, format="json")
        self.assertEqual(unapproved.status_code, 400, unapproved.content)

        payload = {"supplier": self.supplier.pk, "description": "x", "quantity": "1", "expected_date": "2026-10-01"}
        for portal_user in (self.buyer_user, self.supplier_user):
            self.as_user(portal_user)
            self.assertEqual(
                self.client.post(reverse("internal-delivery-notices-list"), payload, format="json").status_code,
                403,
            )

    def test_internal_options_lists_staff_form_choices(self):
        from expenses.models import ExpenseCategory

        ExpenseCategory.objects.create(name="Feed")
        SupplyItem.objects.create(supplier=self.supplier, name="Layer feed 50kg", unit_price=1150)
        dormant_user = User.objects.create_user(username="s11", password="x", role="supplier")
        dormant = Supplier.objects.create(name="Dormant Supplies", user=dormant_user, verification_status="approved")
        SupplyItem.objects.create(supplier=dormant, name="Retired supplier item")
        dormant.is_active = False
        dormant.save()

        self.as_user(self.staff)
        data = self.client.get(reverse("api-v2-internal-options")).json()
        self.assertEqual([c["name"] for c in data["expense_categories"]], ["Feed"])
        self.assertIn("cash", [m["value"] for m in data["payment_methods"]])
        self.assertEqual([s["id"] for s in data["suppliers"]], [self.supplier.pk])
        self.assertEqual(
            [(i["name"], i["supplier"]) for i in data["supply_items"]],
            [("Layer feed 50kg", self.supplier.pk)],
        )
        self.assertEqual(float(data["supply_items"][0]["unit_price"]), 1150.0)

        self.as_user(self.buyer_user)
        self.assertEqual(self.client.get(reverse("api-v2-internal-options")).status_code, 403)

    def test_staff_delivery_queue_filter_and_price_prefill(self):
        item = SupplyItem.objects.create(supplier=self.supplier, name="Corn", unit_price=100)
        announced = DeliveryNotice.objects.create(
            supplier=self.supplier, description="announced one", quantity=1, expected_date="2026-10-01"
        )
        confirmed = DeliveryNotice.objects.create(
            supplier=self.supplier, supply_item=item, description="confirmed one",
            quantity=10, expected_date="2026-10-02", status="confirmed",
        )
        DeliveryNotice.objects.create(
            supplier=self.supplier, description="received one", quantity=1,
            expected_date="2026-10-03", status="received",
        )

        self.as_user(self.staff)
        rows = self.client.get(reverse("internal-delivery-notices-list"), {"status": "open"}).json()["results"]
        self.assertEqual({r["id"] for r in rows}, {announced.pk, confirmed.pk})
        priced = {r["id"]: r["supply_item_price"] for r in rows}
        self.assertEqual(float(priced[confirmed.pk]), 100.0)
        self.assertIsNone(priced[announced.pk])

    def test_receive_requires_an_expense_category(self):
        from expenses.models import ExpenseRecord

        notice = DeliveryNotice.objects.create(
            supplier=self.supplier, description="wheat bran", quantity=5, expected_date="2026-10-01"
        )
        self.as_user(self.staff)
        missing = self.client.post(
            reverse("internal-delivery-notices-receive", args=[notice.pk]),
            {"description": "5 wheat bran", "amount": "500", "expense_date": "2026-10-01"},
            format="json",
        )
        self.assertEqual(missing.status_code, 400, missing.content)
        self.assertIn("category", missing.json())
        notice.refresh_from_db()
        self.assertEqual((notice.status, ExpenseRecord.objects.count()), ("announced", 0))

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


    def test_staff_can_read_dashboard_kpis_without_verification_counts(self):
        OrderRequest.objects.create(
            buyer=self.buyer, product_type="eggs", product_name="Tray eggs",
            quantity=10, requested_date="2026-10-05",
        )
        DeliveryNotice.objects.create(
            supplier=self.supplier, description="feed run", quantity=5, expected_date="2026-10-01",
        )
        Supplier.objects.create(name="Waiting Supplies", verification_status="pending")

        self.as_user(self.staff)
        body = self.client.get(reverse("api-summary")).json()
        self.assertEqual(body["open_requests"], 1)
        self.assertEqual(body["open_deliveries"], 1)
        self.assertIsNone(body["pending_verifications"])
        self.assertEqual(self.client.get(reverse("api-trends")).status_code, 200)

        self.as_user(self.owner)
        self.assertEqual(self.client.get(reverse("api-summary")).json()["pending_verifications"], 1)

        self.as_user(self.buyer_user)
        self.assertEqual(self.client.get(reverse("api-summary")).status_code, 403)

    def test_notification_lists_put_unread_first(self):
        from django.utils import timezone

        for i, read in enumerate([True, False, True, False]):
            note = Notification.objects.create(
                user=self.buyer_user, notification_type="activity",
                title=f"n{i}", message="m", is_read=read,
            )
            # auto_now_add ignores assignment, so backdate through QuerySet.update().
            Notification.objects.filter(pk=note.pk).update(
                created_at=timezone.now() + timezone.timedelta(minutes=i)
            )

        self.as_user(self.buyer_user)
        titles = [r["title"] for r in self.client.get(reverse("api-v2-portal-notifications")).json()["results"]]
        self.assertEqual(titles, ["n3", "n1", "n2", "n0"])

        self.as_user(self.owner)
        older_read = Notification.objects.create(
            user=self.owner, notification_type="low_stock", title="o0", message="m", is_read=True
        )
        older_read.refresh_from_db()
        unread = Notification.objects.create(
            user=self.owner, notification_type="low_stock", title="o1", message="m", is_read=False
        )
        Notification.objects.filter(pk=unread.pk).update(
            created_at=older_read.created_at - timezone.timedelta(days=2)
        )
        titles = [r["title"] for r in self.client.get(reverse("notifications-list")).json()["results"]]
        self.assertEqual(titles, ["o1", "o0"])


class ApiV2InventoryFlowTests(AuthMixin, APITestCase):
    """Receive books stock in; convert deducts stock out; oversell is rejected."""

    def setUp(self):
        self.staff = User.objects.create_user(username="stockstaff2", password="x", role="staff")
        buyer_user = User.objects.create_user(username="b2", password="x", role="buyer")
        self.buyer = Buyer.objects.create(name="Stock Sam", user=buyer_user, verification_status="approved")
        supplier_user = User.objects.create_user(username="s2u", password="x", role="supplier")
        self.supplier = Supplier.objects.create(name="Stock Supplies", user=supplier_user, verification_status="approved")
        from decimal import Decimal

        from expenses.models import ExpenseCategory
        from inventory.models import InventoryCategory, InventoryItem, Unit

        self.ExpenseCategory = ExpenseCategory
        unit = Unit.objects.create(name="Piece", abbreviation="pcs")
        category = InventoryCategory.objects.create(name="Farm products")
        self.item = InventoryItem.objects.create(
            category=category, name="Egg stock", quantity=Decimal("20"), unit=unit,
            reorder_level=Decimal("5"), sales_product_type="eggs",
        )

    def test_receive_books_stock_into_mapped_item(self):
        from decimal import Decimal

        from inventory.models import InventoryTransaction
        from suppliers.models import DeliveryNotice, SupplyItem

        supply = SupplyItem.objects.create(
            supplier=self.supplier, name="Tray eggs", inventory_item=self.item
        )
        notice = DeliveryNotice.objects.create(
            supplier=self.supplier, supply_item=supply, description="tray delivery",
            quantity=Decimal("10"), expected_date="2026-10-01",
        )
        self.as_user(self.staff)
        response = self.client.post(
            reverse("internal-delivery-notices-receive", args=[notice.pk]),
            {"category": self.ExpenseCategory.objects.create(name="Feed").pk,
             "description": "tray delivery", "amount": "300", "expense_date": "2026-10-01"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("30"))
        txn = InventoryTransaction.objects.get(item=self.item)
        self.assertEqual((txn.transaction_type, str(txn.reference)), ("in", f"Delivery Notice #{notice.pk}"))

    def test_receive_can_book_into_selected_stock_row(self):
        from decimal import Decimal

        from inventory.models import InventoryItem
        from suppliers.models import DeliveryNotice

        notice = DeliveryNotice.objects.create(
            supplier=self.supplier, description="ad-hoc rice bran",
            quantity=Decimal("8"), expected_date="2026-10-01",
        )
        target = InventoryItem.objects.create(
            category=self.item.category, name="Rice Bran stock", quantity=Decimal("1"),
            unit=self.item.unit, reorder_level=Decimal("0"),
        )
        self.as_user(self.staff)
        response = self.client.post(
            reverse("internal-delivery-notices-receive", args=[notice.pk]),
            {"category": self.ExpenseCategory.objects.create(name="Feed").pk,
             "description": "ad-hoc rice bran", "amount": "400", "expense_date": "2026-10-01",
             "inventory_item": target.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        target.refresh_from_db()
        notice.refresh_from_db()
        self.assertEqual(target.quantity, Decimal("9"))
        self.assertEqual(notice.inventory_item_id, target.pk)
        # the eggs-mapped item untouched: deduction/booking chose the explicit row
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("20"))

    def test_convert_deducts_stock_and_oversell_returns_400(self):
        from decimal import Decimal

        from inventory.models import InventoryTransaction
        from sales.models import SalesRecord

        order = OrderRequest.objects.create(
            buyer=self.buyer, product_type="eggs", product_name="Eggs", quantity=Decimal("25"),
            requested_date="2026-10-01", status="accepted", quoted_unit_price=Decimal("9.00"),
        )
        self.as_user(self.staff)
        oversell = self.client.post(
            reverse("internal-order-requests-convert", args=[order.pk]),
            {"product_type": "eggs", "product_name": "Eggs", "quantity": "25",
             "unit_price": "9.00", "date_sold": "2026-10-01", "payment_status": "paid",
             "amount_paid": "225"}, format="json",
        )
        self.assertEqual(oversell.status_code, 400)
        self.assertIn("Insufficient stock", oversell.json()["detail"])
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")
        self.assertFalse(SalesRecord.objects.exists())

        order.quantity = Decimal("15")
        order.save()
        convert = self.client.post(
            reverse("internal-order-requests-convert", args=[order.pk]),
            {"product_type": "eggs", "product_name": "Eggs", "quantity": "15",
             "unit_price": "9.00", "date_sold": "2026-10-01", "payment_status": "paid",
             "amount_paid": "135"}, format="json",
        )
        self.assertEqual(convert.status_code, 201, convert.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("5"))
        self.assertEqual(InventoryTransaction.objects.filter(item=self.item).count(), 1)
        from notifications.models import Notification

        self.assertTrue(
            Notification.objects.filter(
                user=self.staff, notification_type="low_stock", title__icontains="Egg stock"
            ).exists()
        )
