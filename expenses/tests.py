from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from expenses.models import ExpenseCategory
from inventory.models import InventoryCategory, InventoryItem, InventoryTransaction, Unit
from suppliers.models import DeliveryNotice, Supplier, SupplyItem

User = get_user_model()


class DeliveryReceiveStockTests(TestCase):
    """PR: receiving a delivery must add mapped supplies to inventory stock."""

    def setUp(self):
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role="staff")
        self.client.force_login(self.staff)
        unit = Unit.objects.create(name="Kilogram", abbreviation="kg")
        category = InventoryCategory.objects.create(name="Feed")
        self.item = InventoryItem.objects.create(
            category=category, name="Layer Mash", quantity=Decimal("10"),
            unit=unit, reorder_level=Decimal("5"),
        )
        self.supplier = Supplier.objects.create(name="Grain Co")
        self.supply = SupplyItem.objects.create(
            supplier=self.supplier, name="Layer feed 50kg", inventory_item=self.item
        )
        self.notice = DeliveryNotice.objects.create(
            supplier=self.supplier, supply_item=self.supply, description="feed sacks",
            quantity=Decimal("10"), expected_date=timezone.localdate(),
        )
        self.expense_category = ExpenseCategory.objects.create(name="Feed purchase")

    def post_receive(self):
        return self.client.post(
            reverse("expenses:delivery_notice_review", args=[self.notice.pk]),
            {
                "action": "receive", "category": self.expense_category.pk,
                "description": "feed sacks", "amount": "1150.00",
                "expense_date": str(timezone.localdate()), "payment_method": "cash",
            },
        )

    def test_receive_adds_stock_and_transaction(self):
        response = self.post_receive()
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("20"))
        txn = InventoryTransaction.objects.get(item=self.item)
        self.assertEqual(
            (txn.transaction_type, str(txn.reference)),
            ("in", f"Delivery Notice #{self.notice.pk}"),
        )

    def test_receive_without_mapping_leaves_stock_untouched(self):
        self.supply.inventory_item = None
        self.supply.save()
        response = self.post_receive()
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("10"))
        self.assertFalse(InventoryTransaction.objects.exists())

    def test_receive_deducts_nothing_on_reject(self):
        response = self.client.post(
            reverse("expenses:delivery_notice_review", args=[self.notice.pk]),
            {"action": "reject", "note": "wrong goods"},
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("10"))
        self.assertFalse(InventoryTransaction.objects.exists())


class AdHocReceiveBookingTests(TestCase):
    """Ad-hoc orders skip the catalog; receive-time booking decides the permanent stock row."""

    def setUp(self):
        self.staff = User.objects.create_user(username="adhocstaff", password="pass12345", role="staff")
        self.client.force_login(self.staff)
        self.unit = Unit.objects.create(name="Sack", abbreviation="sk")
        self.category = InventoryCategory.objects.create(name="Feed")
        self.supplier = Supplier.objects.create(name="Rice Mill", is_active=True, verification_status="approved")
        self.expense_category = ExpenseCategory.objects.create(name="Feed purchase")

    def _receive_payload(self, **overrides):
        data = {
            "action": "receive", "category": self.expense_category.pk,
            "description": "rice bran sacks", "amount": "2000.00",
            "expense_date": str(timezone.localdate()), "payment_method": "cash",
        }
        data.update(overrides)
        return data

    def test_ad_hoc_farm_order_needs_no_catalog_item(self):
        response = self.client.post(
            reverse("expenses:delivery_notice_create"),
            {
                "supplier": self.supplier.pk, "supply_item": "",
                "description": "5 sacks rice bran", "quantity": "5",
                "expected_date": str(timezone.localdate()),
            },
        )
        self.assertEqual(response.status_code, 302)
        notice = DeliveryNotice.objects.get()
        self.assertIsNone(notice.supply_item_id)
        self.assertEqual(notice.origin, "farm")

    def test_receive_creates_new_stock_item_and_books_it(self):
        notice = DeliveryNotice.objects.create(
            supplier=self.supplier, description="5 sacks rice bran",
            quantity=Decimal("5"), expected_date=timezone.localdate(),
        )
        response = self.client.post(
            reverse("expenses:delivery_notice_review", args=[notice.pk]),
            self._receive_payload(
                new_item_name="Rice Bran", new_item_unit=self.unit.pk,
                new_item_category=self.category.pk,
            ),
        )
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(name="Rice Bran")
        notice.refresh_from_db()
        self.assertEqual(notice.inventory_item_id, item.pk)
        self.assertEqual(item.quantity, Decimal("5"))

    def test_new_item_with_duplicate_name_is_refused(self):
        InventoryItem.objects.create(
            category=self.category, name="rice bran", quantity=1, unit=self.unit
        )
        notice = DeliveryNotice.objects.create(
            supplier=self.supplier, description="extra bran",
            quantity=Decimal("4"), expected_date=timezone.localdate(),
        )
        response = self.client.post(
            reverse("expenses:delivery_notice_review", args=[notice.pk]),
            self._receive_payload(
                new_item_name="Rice Bran", new_item_unit=self.unit.pk,
                new_item_category=self.category.pk,
            ),
            headers={"hx-request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists in stock")
        notice.refresh_from_db()
        self.assertEqual(notice.status, "announced")
        self.assertEqual(InventoryItem.objects.filter(name__iexact="rice bran").count(), 1)

    def test_explicit_booking_overrides_catalog_mapping(self):
        mapped = InventoryItem.objects.create(
            category=self.category, name="Layer Mash", quantity=Decimal("10"), unit=self.unit
        )
        other = InventoryItem.objects.create(
            category=self.category, name="Starter Mash", quantity=Decimal("10"), unit=self.unit
        )
        supply = SupplyItem.objects.create(
            supplier=self.supplier, name="feed", inventory_item=mapped
        )
        notice = DeliveryNotice.objects.create(
            supplier=self.supplier, supply_item=supply, description="feed delivery",
            quantity=Decimal("6"), expected_date=timezone.localdate(),
        )
        response = self.client.post(
            reverse("expenses:delivery_notice_review", args=[notice.pk]),
            self._receive_payload(inventory_item=other.pk),
        )
        self.assertEqual(response.status_code, 302)
        mapped.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(mapped.quantity, Decimal("10"))
        self.assertEqual(other.quantity, Decimal("16"))


class SupplierReceiptApiTests(TestCase):
    """Admin-uploaded expense receipts must be exposed to the supplier mobile API."""

    def test_admin_uploaded_receipt_exposed_on_supplier_purchases_and_deliveries(self):
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        admin = User.objects.create_user(username="rcpt_admin", password="StrongPass123!", role="admin")
        sup_user = User.objects.create_user(
            username="rcpt_sup", password="StrongPass123!", role="supplier", is_active=True
        )
        supplier = Supplier.objects.create(
            name="Tambulig Feed Supply",
            user=sup_user,
            verification_status="approved",
            is_active=True,
        )
        cat = ExpenseCategory.objects.create(name="Receipt Test Feeds")
        notice = DeliveryNotice.objects.create(
            supplier=supplier,
            description="20 sacks starter mash",
            quantity=Decimal("20"),
            expected_date=timezone.localdate(),
        )

        # Tiny valid 1x1 PNG
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        receipt_file = SimpleUploadedFile("delivery_receipt.png", png_bytes, content_type="image/png")

        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                self.client.force_login(admin)
                resp = self.client.post(
                    reverse("expenses:delivery_notice_review", args=[notice.pk]),
                    {
                        "action": "receive",
                        "category": cat.pk,
                        "description": "20 sacks starter mash",
                        "amount": "24000.00",
                        "expense_date": str(timezone.localdate()),
                        "payment_method": "gcash",
                        "receipt": receipt_file,
                    },
                )
                self.assertEqual(resp.status_code, 302)
                notice.refresh_from_db()
                self.assertEqual(notice.status, "received")
                self.assertIsNotNone(notice.expense_record)
                self.assertTrue(bool(notice.expense_record.receipt))

                token, _ = Token.objects.get_or_create(user=sup_user)
                api = APIClient()
                api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

                # Purchases endpoint includes receipt_url & receipt_name
                purchases_resp = api.get("/api/v2/portal/purchase-history/")
                self.assertEqual(purchases_resp.status_code, 200)
                p_rows = purchases_resp.data["results"] if isinstance(purchases_resp.data, dict) else purchases_resp.data
                self.assertEqual(len(p_rows), 1)
                self.assertIn("/media/receipts/", p_rows[0]["receipt_url"])
                self.assertTrue(p_rows[0]["receipt_name"].endswith(".png"))

                # Deliveries endpoint also includes receipt_url, receipt_name & expense_amount
                deliv_resp = api.get("/api/v2/portal/delivery-notices/")
                self.assertEqual(deliv_resp.status_code, 200)
                d_rows = deliv_resp.data["results"] if isinstance(deliv_resp.data, dict) else deliv_resp.data
                self.assertEqual(len(d_rows), 1)
                self.assertIn("/media/receipts/", d_rows[0]["receipt_url"])
                self.assertEqual(str(d_rows[0]["expense_amount"]), "24000.00")

                # File is saved on disk at MEDIA_ROOT
                import os

                self.assertTrue(os.path.exists(notice.expense_record.receipt.path))
                self.assertTrue(p_rows[0]["receipt_url"].startswith("http://testserver/media/receipts/"))
