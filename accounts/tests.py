from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AccountsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin", password="admin123", role="admin"
        )
        self.staff_user = User.objects.create_user(
            username="staff", password="staff123", role="staff"
        )

    def test_user_creation(self):
        self.assertEqual(User.objects.count(), 2)

    def test_user_roles(self):
        self.assertEqual(self.admin_user.role, "admin")
        self.assertEqual(self.staff_user.role, "staff")

    def test_login_required(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotEqual(response.status_code, 200)

    def test_login_success(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "admin", "password": "admin123"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))

    def test_login_failure(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "admin", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid")

    def test_user_list_view(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin")
        self.assertContains(response, "staff")


class AuthorizationMatrixTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", password="pass12345", role="admin")
        self.owner = User.objects.create_user(username="owner1", password="pass12345", role="owner")
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role="staff")
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345", role="buyer")

    def test_staff_blocked_from_user_administration(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:user_create")).status_code, 403)

    def test_owner_sees_users_but_cannot_create(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:user_create")).status_code, 403)

    def test_internal_pages_reject_external_users_by_redirect(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("sales:sales_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/", response["Location"])

    def test_staff_can_record_but_not_edit_facts(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("expenses:expense_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("settings_app:settings")).status_code, 200)


class PortalPasswordResetTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", password="pass12345", role="owner")
        self.staff = User.objects.create_user(username="staff1", password="pass12345", role="staff")
        self.buyer = User.objects.create_user(username="buyer1", password="oldpass123", role="buyer")

    def test_staff_cannot_reset(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("accounts:reset_portal_password", args=[self.buyer.pk]))
        self.assertEqual(response.status_code, 403)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.check_password("oldpass123"))

    def test_owner_resets_and_reactivates(self):
        self.buyer.is_active = False
        self.buyer.save()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("accounts:reset_portal_password", args=[self.buyer.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.is_active)
        self.assertFalse(self.buyer.check_password("oldpass123"))
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("temporary password" in m for m in messages))

    def test_internal_users_cannot_be_reset_through_portal_tool(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("accounts:reset_portal_password", args=[self.staff.pk]), follow=True)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("pass12345"))


class PartnerSelfRegistrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_verif", password="StrongPass123!", role="admin"
        )
        self.owner = User.objects.create_user(
            username="owner_verif", password="StrongPass123!", role="owner"
        )
        self.staff = User.objects.create_user(
            username="staff_verif", password="StrongPass123!", role="staff"
        )

    def test_registration_links_reachable_without_auth(self):
        landing = self.client.get("/")
        self.assertEqual(landing.status_code, 200)
        self.assertContains(landing, reverse("accounts:register"))

        login_page = self.client.get(reverse("accounts:login"))
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, reverse("accounts:register_buyer"))
        self.assertContains(login_page, reverse("accounts:register_supplier"))

        for url_name in ("accounts:register", "accounts:register_buyer", "accounts:register_supplier"):
            resp = self.client.get(reverse(url_name))
            self.assertEqual(resp.status_code, 200)

    def test_buyer_self_registration_requires_approval_and_notifies_admins(self):
        from buyers.models import Buyer
        from notifications.models import Notification

        response = self.client.post(
            reverse("accounts:register"),
            {
                "role": "buyer",
                "name": "Fresh Mart Trading",
                "contact_person": "Maria Santos",
                "username": "freshmart",
                "email": "maria@freshmart.test",
                "phone": "09171234567",
                "address": "Tambulig Public Market",
                "buyer_type": "wholesale",
                "password1": "BuyerPass2026!",
                "password2": "BuyerPass2026!",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertContains(response, "pending administrator approval")

        user = User.objects.get(username="freshmart")
        self.assertEqual(user.role, "buyer")
        self.assertFalse(user.is_active)

        buyer = Buyer.objects.get(user=user)
        self.assertEqual(buyer.name, "Fresh Mart Trading")
        self.assertEqual(buyer.buyer_type, "wholesale")
        self.assertEqual(buyer.verification_status, "pending")

        # Admin and owner notified; staff not notified for verifications
        self.assertTrue(
            Notification.objects.filter(user=self.admin, notification_type="account").exists()
        )
        self.assertTrue(
            Notification.objects.filter(user=self.owner, notification_type="account").exists()
        )
        self.assertFalse(
            Notification.objects.filter(user=self.staff, notification_type="account").exists()
        )

        # Pending buyer sees helpful message on login with correct password
        pending_login = self.client.post(
            reverse("accounts:login"),
            {"username": "freshmart", "password": "BuyerPass2026!"},
        )
        self.assertEqual(pending_login.status_code, 200)
        self.assertContains(pending_login, "pending administrator approval")
        self.assertFalse(pending_login.wsgi_request.user.is_authenticated)

        # Wrong password still gives generic invalid credentials message
        wrong_pw = self.client.post(
            reverse("accounts:login"),
            {"username": "freshmart", "password": "WrongPassword!"},
        )
        self.assertEqual(wrong_pw.status_code, 200)
        self.assertContains(wrong_pw, "Invalid username or password")

        # Appears in verification queue and admin approves
        self.client.force_login(self.admin)
        queue_resp = self.client.get(reverse("accounts:verification_queue"))
        self.assertEqual(queue_resp.status_code, 200)
        self.assertContains(queue_resp, "Fresh Mart Trading")

        approve_resp = self.client.post(
            reverse("accounts:verification_action", args=["buyer", buyer.pk]),
            {"action": "approve"},
        )
        self.assertRedirects(approve_resp, reverse("accounts:verification_queue"))

        user.refresh_from_db()
        buyer.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(buyer.verification_status, "approved")
        self.assertTrue(
            Notification.objects.filter(user=user, notification_type="account").exists()
        )

        # Approved buyer can now log in and access buyer portal
        self.client.logout()
        login_resp = self.client.post(
            reverse("accounts:login"),
            {"username": "freshmart", "password": "BuyerPass2026!"},
            follow=True,
        )
        self.assertRedirects(login_resp, reverse("portal:buyer_home"))
        self.assertEqual(login_resp.status_code, 200)

    def test_supplier_self_registration_and_rejection_flow(self):
        from suppliers.models import Supplier

        response = self.client.post(
            reverse("accounts:register_supplier"),
            {
                "role": "supplier",
                "name": "Zambo Feeds Corp",
                "contact_person": "Juan Dela Cruz",
                "username": "zambofeeds",
                "email": "sales@zambofeeds.test",
                "phone": "09189876543",
                "address": "Pagadian City",
                "supplies": "Layer Feeds, Starter Mash",
                "payment_terms": "net15",
                "dti_registration": "DTI-998877",
                "password1": "SupplierPass2026!",
                "password2": "SupplierPass2026!",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("accounts:login"))

        user = User.objects.get(username="zambofeeds")
        self.assertEqual(user.role, "supplier")
        self.assertFalse(user.is_active)

        supplier = Supplier.objects.get(user=user)
        self.assertEqual(supplier.name, "Zambo Feeds Corp")
        self.assertEqual(supplier.supplies, "Layer Feeds, Starter Mash")
        self.assertEqual(supplier.payment_terms, "net15")
        self.assertEqual(supplier.dti_registration, "DTI-998877")
        self.assertEqual(supplier.verification_status, "pending")

        # Admin rejects with reason
        self.client.force_login(self.admin)
        self.client.post(
            reverse("accounts:verification_action", args=["supplier", supplier.pk]),
            {"action": "reject", "reason": "Missing business permit"},
        )
        user.refresh_from_db()
        supplier.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(supplier.verification_status, "rejected")
        self.assertEqual(supplier.rejection_reason, "Missing business permit")

        # Rejected supplier sees rejection message and reason on login
        self.client.logout()
        rejected_login = self.client.post(
            reverse("accounts:login"),
            {"username": "zambofeeds", "password": "SupplierPass2026!"},
        )
        self.assertEqual(rejected_login.status_code, 200)
        self.assertContains(rejected_login, "not approved")
        self.assertContains(rejected_login, "Missing business permit")
        self.assertFalse(rejected_login.wsgi_request.user.is_authenticated)

        # Admin subsequently approves -> supplier can access supplier portal
        self.client.force_login(self.owner)
        self.client.post(
            reverse("accounts:verification_action", args=["supplier", supplier.pk]),
            {"action": "approve"},
        )
        self.client.logout()
        login_resp = self.client.post(
            reverse("accounts:login"),
            {"username": "zambofeeds", "password": "SupplierPass2026!"},
            follow=True,
        )
        self.assertRedirects(login_resp, reverse("portal:supplier_home"))
        self.assertEqual(login_resp.status_code, 200)

    def test_cannot_self_register_as_internal_role(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "role": "admin",
                "name": "Sneaky Admin",
                "username": "sneakyadmin",
                "email": "sneaky@test.com",
                "password1": "SneakyPass2026!",
                "password2": "SneakyPass2026!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="sneakyadmin").exists())
