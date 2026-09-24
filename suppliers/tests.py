from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from expenses.models import ExpenseCategory, ExpenseRecord
from suppliers.models import DeliveryNotice, Supplier, SupplyItem

User = get_user_model()


def make_supplier_user(username="supplier1"):
    return User.objects.create_user(username=username, password="pass12345", role="supplier")


class SupplierPortalTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role="staff")
        self.supplier_user = make_supplier_user()
        self.supplier = Supplier.objects.create(
            name="Davao Feeds", phone="09111", email="d@f.ph",
            user=self.supplier_user, verification_status="approved",
        )

    def test_catalog_crud_scoped_to_owner(self):
        self.client.force_login(self.supplier_user)
        response = self.client.post(reverse("portal:supplier_catalog_create"), {
            "name": "Layer feed 50kg", "category": "Feed", "unit_price": "1150",
            "availability": "in_stock",
        })
        self.assertEqual(response.status_code, 302)
        item = SupplyItem.objects.get(supplier=self.supplier)
        self.assertEqual(item.name, "Layer feed 50kg")

    def test_cannot_edit_other_suppliers_item(self):
        other_user = make_supplier_user("supplier2")
        other = Supplier.objects.create(name="Other Supply Co", user=other_user, verification_status="approved")
        item = SupplyItem.objects.create(supplier=other, name="Secret mash")
        self.client.force_login(self.supplier_user)
        response = self.client.get(reverse("portal:supplier_catalog_update", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_delivery_notice_flow(self):
        item = SupplyItem.objects.create(supplier=self.supplier, name="Layer feed 50kg", unit_price=1150)
        self.client.force_login(self.supplier_user)
        response = self.client.post(reverse("portal:supplier_delivery_create"), {
            "supply_item": item.pk, "description": "20 sacks of layer feed",
            "quantity": "20", "expected_date": "2026-09-26",
        })
        self.assertEqual(response.status_code, 302)
        notice = DeliveryNotice.objects.get(supplier=self.supplier)
        self.assertEqual(notice.status, "announced")
        self.assertTrue(self.staff.notifications.filter(notification_type="delivery_notice").exists())

        category = ExpenseCategory.objects.create(name="Feed")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("expenses:delivery_notice_review", args=[notice.pk]), {
            "action": "receive", "category": category.pk,
            "description": "20 sacks layer feed from Davao Feeds",
            "amount": "23000", "expense_date": "2026-09-26", "payment_method": "cash",
        })
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        record = ExpenseRecord.objects.get(supplier=self.supplier)
        self.assertEqual(notice.status, "received")
        self.assertEqual(notice.expense_record_id, record.pk)
        self.assertTrue(self.supplier_user.notifications.filter(title__contains="received").exists())

    def test_other_supplier_notices_not_visible(self):
        other_user = make_supplier_user("supplier2")
        other = Supplier.objects.create(name="Other Supply Co", user=other_user, verification_status="approved")
        DeliveryNotice.objects.create(supplier=other, description="hidden batch", quantity=3, expected_date="2026-09-27")
        self.client.force_login(self.supplier_user)
        response = self.client.get(reverse("portal:supplier_deliveries"))
        self.assertNotContains(response, "hidden batch")


class SupplierAccountTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role="staff")
        self.admin = User.objects.create_user(username="admin1", password="pass12345", role="admin")

    def test_staff_creates_account(self):
        supplier = Supplier.objects.create(name="Doctom Vet", email="v@v.ph")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("suppliers:supplier_create_account", args=[supplier.pk]))
        self.assertEqual(response.status_code, 302)
        supplier.refresh_from_db()
        self.assertEqual(supplier.user.role, "supplier")
        self.assertEqual(supplier.verification_status, "approved")

    def test_verification_approve_activates_user(self):
        user = make_supplier_user()
        user.is_active = False
        user.save()
        supplier = Supplier.objects.create(name="New Guy Supplies", user=user, verification_status="pending")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:verification_action", args=["supplier", supplier.pk]),
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        supplier.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(supplier.verification_status, "approved")
        self.assertTrue(user.is_active)

    def test_staff_cannot_access_verification_queue(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:verification_queue"))
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_deactivate_supplier(self):
        supplier = Supplier.objects.create(name="Doctom Vet", email="v@v.ph", is_active=True)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("suppliers:supplier_deactivate_account", args=[supplier.pk]))
        self.assertEqual(response.status_code, 403)
        supplier.refresh_from_db()
        self.assertTrue(supplier.is_active)

    def test_owner_can_deactivate_supplier(self):
        owner = User.objects.create_user(username="owner1", password="pass12345", role="owner")
        supplier_user = User.objects.create_user(username="supuser", password="pass12345", role="supplier")
        supplier = Supplier.objects.create(name="Doctom Vet", email="v@v.ph", user=supplier_user, is_active=True)
        self.client.force_login(owner)
        response = self.client.post(reverse("suppliers:supplier_deactivate_account", args=[supplier.pk]))
        self.assertEqual(response.status_code, 302)
        supplier.refresh_from_db()
        supplier_user.refresh_from_db()
        self.assertFalse(supplier.is_active)
        self.assertFalse(supplier_user.is_active)


class FarmProcurementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role="staff")
        self.supplier_user = make_supplier_user()
        self.supplier = Supplier.objects.create(
            name="Davao Feeds", user=self.supplier_user, verification_status="approved",
        )
        self.item = SupplyItem.objects.create(supplier=self.supplier, name="Layer feed 50kg", unit_price=1150)

    def _farm_order(self):
        self.client.force_login(self.staff)
        return self.client.post(reverse("expenses:delivery_notice_create"), {
            "supplier": self.supplier.pk, "supply_item": self.item.pk,
            "description": "30 sacks layer feed", "quantity": "30",
            "expected_date": "2026-10-01",
        })

    def test_staff_places_farm_order(self):
        response = self._farm_order()
        self.assertEqual(response.status_code, 302)
        notice = DeliveryNotice.objects.get(supplier=self.supplier)
        self.assertEqual(notice.origin, "farm")
        self.assertEqual(notice.status, "announced")
        self.assertEqual(notice.created_by, self.staff)
        self.assertTrue(self.supplier_user.notifications.filter(title__contains="ordered").exists())

    def test_catalog_item_must_belong_to_selected_supplier(self):
        other_user = make_supplier_user("supplier2")
        other = Supplier.objects.create(name="Other Co", user=other_user, verification_status="approved")
        other_item = SupplyItem.objects.create(supplier=other, name="Their mash")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("expenses:delivery_notice_create"), {
            "supplier": self.supplier.pk, "supply_item": other_item.pk,
            "description": "", "quantity": "5", "expected_date": "2026-10-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DeliveryNotice.objects.exists())

    def test_supplier_confirms_and_adjusts_farm_order(self):
        self._farm_order()
        notice = DeliveryNotice.objects.get(supplier=self.supplier)
        self.client.force_login(self.supplier_user)
        response = self.client.post(reverse("portal:supplier_delivery_respond", args=[notice.pk]), {
            "expected_date": "2026-10-03", "supplier_note": "Stock arriving Tuesday",
        })
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        self.assertEqual(str(notice.expected_date), "2026-10-03")
        self.assertEqual(notice.supplier_note, "Stock arriving Tuesday")
        self.assertTrue(self.staff.notifications.filter(title__contains="confirmed").exists())

    def test_supplier_cannot_respond_to_own_announcement(self):
        self.client.force_login(self.supplier_user)
        self.client.post(reverse("portal:supplier_delivery_create"), {
            "supply_item": self.item.pk, "description": "self announced",
            "quantity": "10", "expected_date": "2026-10-01",
        })
        notice = DeliveryNotice.objects.get(description="self announced")
        response = self.client.post(reverse("portal:supplier_delivery_respond", args=[notice.pk]), {
            "expected_date": "2026-10-05", "supplier_note": "hijack",
        })
        notice.refresh_from_db()
        self.assertEqual(str(notice.expected_date), "2026-10-01")
        self.assertIsNone(notice.supplier_note)
        self.assertRedirects(response, reverse("portal:supplier_deliveries"))

    def test_supplier_cancels_own_announcement(self):
        self.client.force_login(self.supplier_user)
        self.client.post(reverse("portal:supplier_delivery_create"), {
            "supply_item": self.item.pk, "description": "cancel me",
            "quantity": "4", "expected_date": "2026-10-02",
        })
        notice = DeliveryNotice.objects.get(description="cancel me")
        response = self.client.post(reverse("portal:supplier_delivery_cancel", args=[notice.pk]), {"note": "truck broke down"})
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        self.assertEqual(notice.status, "rejected")
        self.assertEqual(notice.supplier_note, "truck broke down")
        self.assertTrue(self.staff.notifications.filter(title__contains="cancelled").exists())

    def test_supplier_cannot_cancel_farm_order(self):
        self._farm_order()
        notice = DeliveryNotice.objects.get(supplier=self.supplier)
        self.client.force_login(self.supplier_user)
        self.client.post(reverse("portal:supplier_delivery_cancel", args=[notice.pk]))
        notice.refresh_from_db()
        self.assertEqual(notice.status, "announced")
