from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from buyers.models import Buyer, OrderRequest
from notifications.models import ActivityLog
from rest_framework.test import APIClient
from sales.models import Product, SalesRecord

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


class SaleStockDeductionTests(TestCase):
    """Sales against a mapped product type deduct inventory; oversells are blocked."""

    def setUp(self):
        self.staff = make_user("stockstaff", "staff")
        self.owner = make_user("stockowner", "owner")
        self.buyer = Buyer.objects.create(name="Tray Tina")
        from inventory.models import InventoryCategory, InventoryItem, InventoryTransaction, Unit

        unit = Unit.objects.create(name="Piece", abbreviation="pcs")
        category = InventoryCategory.objects.create(name="Farm products")
        self.item = InventoryItem.objects.create(
            category=category, name="Eggs stock", quantity=Decimal("20"),
            unit=unit, reorder_level=Decimal("5"), sales_product_type="eggs",
        )
        self.InventoryTransaction = InventoryTransaction

    def _make_accepted(self, quantity="10"):
        return OrderRequest.objects.create(
            buyer=self.buyer, product_type="eggs", product_name="Eggs",
            quantity=Decimal(quantity), requested_date=timezone.localdate(),
            status="accepted", quoted_unit_price=Decimal("8.00"),
        )

    def test_direct_sale_deducts_stock(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:sales_create"),
            sales_form_data(quantity="10", amount_paid="80.00"),
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("10"))
        sale = SalesRecord.objects.get()
        txn = self.InventoryTransaction.objects.get(item=self.item)
        self.assertEqual((txn.transaction_type, str(txn.reference)), ("out", f"Sales Record #{sale.pk}"))

    def test_conversion_deducts_stock(self):
        order = self._make_accepted()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(quantity="10", unit_price="8.00", amount_paid="80.00"),
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("10"))

    def test_oversell_blocks_conversion_even_for_owner(self):
        order = self._make_accepted(quantity="50")
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sales:order_request_convert", args=[order.pk]),
            sales_form_data(quantity="50", unit_price="8.00", amount_paid="400.00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insufficient stock")
        self.assertFalse(SalesRecord.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("20"))

    def test_unmapped_product_type_deducts_nothing(self):
        self.item.sales_product_type = None
        self.item.save()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("sales:sales_create"),
            sales_form_data(quantity="10", amount_paid="80.00"),
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("20"))
        self.assertFalse(self.InventoryTransaction.objects.exists())


class ProductCatalogManagementTests(TestCase):
    """Farm catalog: internal users may read; only owner/admin may manage products."""

    def setUp(self):
        self.staff = make_user("pstaff", "staff")
        self.owner = make_user("powner", "owner")
        self.buyer_user = make_user("pbuyer", "buyer")
        self.buyer = Buyer.objects.create(
            name="Catalog Buyer", user=self.buyer_user, verification_status="approved"
        )
        self.product = Product.objects.create(
            name="Eggs (tray)", product_type="eggs", unit_label="tray",
            unit_price=Decimal("560.00"),
        )

    def test_staff_can_view_but_not_manage(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("sales:product_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("sales:product_create")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("sales:product_update", args=[self.product.pk]), {}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("sales:product_toggle", args=[self.product.pk])
            ).status_code,
            403,
        )

    def test_owner_creates_product_and_creator_is_tracked(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sales:product_create"),
            {
                "name": "Dressed chicken",
                "product_type": "dressed",
                "unit_label": "kg",
                "unit_price": "280.00",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("sales:product_list"))
        product = Product.objects.get(name="Dressed chicken")
        self.assertEqual(product.created_by, self.owner)
        self.assertTrue(product.is_active)
        self.assertTrue(
            ActivityLog.objects.filter(
                model_name="Product", action="create", object_id=product.pk
            ).exists()
        )

    def test_duplicate_name_is_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sales:product_create"),
            {
                "name": "eggs (TRAY)",
                "product_type": "eggs",
                "unit_label": "tray",
                "unit_price": "560.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A product with this name already exists.")
        self.assertEqual(Product.objects.count(), 1)

    def test_owner_edits_price(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sales:product_update", args=[self.product.pk]),
            {
                "name": "Eggs (tray)",
                "product_type": "eggs",
                "unit_label": "tray",
                "unit_price": "575.00",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("sales:product_list"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.unit_price, Decimal("575.00"))

    def test_toggle_deactivation_removes_product_from_buyer_feed(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sales:product_toggle", args=[self.product.pk])
        )
        self.assertRedirects(response, reverse("sales:product_list"))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

        api = APIClient()
        api.force_authenticate(user=self.buyer_user)
        feed = api.get(reverse("api-v2-portal-products"))
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.json(), [])
