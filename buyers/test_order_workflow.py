from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from buyers.models import Buyer, OrderRequest
from buyers.workflow import get_workflow_rules, save_workflow_rules
from sales.models import SalesRecord

User = get_user_model()


class OrderWorkflowAutomationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="wf_admin", password="pw", role="admin", is_staff=True, is_superuser=True
        )
        self.buyer_user = User.objects.create_user(
            username="wf_buyer", password="pw", role="buyer", is_active=True
        )
        self.buyer = Buyer.objects.create(
            name="Tambulig Buyer",
            user=self.buyer_user,
            verification_status="approved",
            is_active=True,
        )
        self.order = OrderRequest.objects.create(
            buyer=self.buyer,
            product_type="chicken",
            product_name="Live Chicken",
            quantity=Decimal("5.00"),
            requested_unit_price=Decimal("200.00"),
            created_by=self.buyer_user,
        )

    def test_buyer_order_starts_pending_approval_and_tracks_6_stages(self):
        self.assertEqual(self.order.status, "submitted")
        self.assertEqual(self.order.get_status_display(), "Pending Approval")
        labels = [label for label, _ in self.order.timeline()]
        self.assertEqual(
            labels,
            ["Pending Approval", "Approved", "Processing", "Out for Delivery", "Delivered", "Completed"],
        )

    def test_admin_progression_auto_completes_on_delivered_and_records_sale(self):
        self.client.force_login(self.admin)
        review_url = reverse("sales:order_request_review", args=[self.order.pk])

        # Approve -> Processing -> Out for Delivery -> Delivered (auto-completes!)
        for action, expected_status in [
            ("approve", "approved"),
            ("process", "processing"),
            ("out_for_delivery", "out_for_delivery"),
            ("deliver", "completed"),
        ]:
            res = self.client.post(review_url, {"action": action})
            self.assertEqual(res.status_code, 302)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, expected_status)

        self.assertIsNotNone(self.order.sales_record_id)
        self.assertEqual(self.order.sales_record.total_amount, Decimal("1000.00"))
        self.assertEqual(self.order.sales_record.payment_status, "paid")
        self.assertTrue(SalesRecord.objects.filter(pk=self.order.sales_record_id).exists())

    def test_configurable_rule_can_pause_at_delivered_until_buyer_confirms(self):
        save_workflow_rules(
            auto_complete_on_delivered=False,
            auto_complete_on_buyer_accept=True,
            auto_create_sale_on_complete=True,
        )
        self.assertFalse(get_workflow_rules()["order_auto_complete_on_delivered"])

        self.client.force_login(self.admin)
        review_url = reverse("sales:order_request_review", args=[self.order.pk])
        self.client.post(review_url, {"action": "approve"})
        self.client.post(review_url, {"action": "deliver"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "delivered")
        self.assertIsNone(self.order.sales_record_id)

        # Buyer confirms receipt -> automatically completes & creates Sale
        self.client.force_login(self.buyer_user)
        respond_url = reverse("portal:buyer_request_respond", args=[self.order.pk])
        res = self.client.post(respond_url, {"action": "confirm_received"})
        self.assertEqual(res.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "completed")
        self.assertIsNotNone(self.order.sales_record_id)

    def test_buyer_accept_auto_completes_when_rule_enabled(self):
        self.order.status = "quoted"
        self.order.quoted_unit_price = Decimal("210.00")
        self.order.save()

        self.client.force_login(self.buyer_user)
        respond_url = reverse("portal:buyer_request_respond", args=[self.order.pk])
        res = self.client.post(respond_url, {"action": "accept"})
        self.assertEqual(res.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "completed")
        self.assertIsNotNone(self.order.sales_record_id)
        self.assertEqual(self.order.sales_record.total_amount, Decimal("1050.00"))

    def test_admin_can_configure_workflow_rules_from_settings_ui(self):
        self.client.force_login(self.admin)
        url = reverse("settings_app:order_workflow_settings")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Order Workflow Automation")

        res = self.client.post(
            url,
            {
                "order_auto_complete_on_delivered": "on",
                "order_auto_create_sale_on_complete": "on",
            },
        )
        self.assertRedirects(res, url)
        rules = get_workflow_rules()
        self.assertTrue(rules["order_auto_complete_on_delivered"])
        self.assertFalse(rules["order_auto_complete_on_buyer_accept"])
        self.assertTrue(rules["order_auto_create_sale_on_complete"])

    def test_delivery_receipt_is_printable_by_admin_only_and_blocked_for_buyer_and_staff(self):
        # Complete the order first
        self.client.force_login(self.admin)
        review_url = reverse("sales:order_request_review", args=[self.order.pk])
        self.client.post(review_url, {"action": "approve"})
        self.client.post(review_url, {"action": "deliver"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "completed")

        receipt_url = reverse("sales:order_request_receipt_print", args=[self.order.pk])

        # Admin can print the Delivery Verification Receipt
        res_admin = self.client.get(receipt_url)
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, "Delivery Verification Receipt")
        self.assertContains(res_admin, self.order.request_number)
        self.assertContains(res_admin, "window.print()")

        # Buyer cannot access or print the receipt (redirected to portal or 403)
        self.client.force_login(self.buyer_user)
        res_buyer = self.client.get(receipt_url)
        self.assertIn(res_buyer.status_code, (302, 403))
        buyer_detail = self.client.get(reverse("portal:buyer_request_detail", args=[self.order.pk]))
        self.assertEqual(buyer_detail.status_code, 200)
        self.assertNotContains(buyer_detail, receipt_url)

        # Staff cannot print the receipt (403)
        staff_user = User.objects.create_user(username="wf_staff", password="pw", role="staff")
        self.client.force_login(staff_user)
        res_staff = self.client.get(receipt_url)
        self.assertEqual(res_staff.status_code, 403)

    def test_buyer_accepts_out_for_delivery_then_admin_marks_delivered_and_prints_receipt(self):
        # Admin: Approve -> Processing -> Out for Delivery
        self.client.force_login(self.admin)
        review_url = reverse("sales:order_request_review", args=[self.order.pk])
        self.client.post(review_url, {"action": "approve"})
        self.client.post(review_url, {"action": "process"})
        self.client.post(review_url, {"action": "out_for_delivery"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "out_for_delivery")

        # Buyer accepts order while Out for Delivery -> moves to accepted (ready for admin Mark Delivered)
        self.client.force_login(self.buyer_user)
        respond_url = reverse("portal:buyer_request_respond", args=[self.order.pk])
        res = self.client.post(respond_url, {"action": "confirm_received"})
        self.assertEqual(res.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "accepted")

        # Admin marks Delivered -> auto-completes & receipt is printable
        self.client.force_login(self.admin)
        self.client.post(review_url, {"action": "deliver"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "completed")
        self.assertIsNotNone(self.order.sales_record_id)
        receipt_res = self.client.get(reverse("sales:order_request_receipt_print", args=[self.order.pk]))
        self.assertEqual(receipt_res.status_code, 200)
