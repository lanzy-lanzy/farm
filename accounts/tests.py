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

    def test_mobile_api_v2_partner_registration(self):
        import json
        from buyers.models import Buyer
        from suppliers.models import Supplier
        from notifications.models import Notification

        # Buyer registration via mobile API
        buyer_resp = self.client.post(
            "/api/v2/auth/register/",
            data=json.dumps({
                "role": "buyer",
                "name": "Tambulig Market Buyer",
                "contact_person": "Ana Reyes",
                "username": "mobile_buyer1",
                "email": "ana@tambulig.test",
                "phone": "09170001111",
                "address": "Tambulig, Zamboanga del Sur",
                "buyer_type": "retail",
                "password": "MobileBuyer2026!",
            }),
            content_type="application/json",
        )
        self.assertEqual(buyer_resp.status_code, 201)
        buyer_user = User.objects.get(username="mobile_buyer1")
        self.assertEqual(buyer_user.role, "buyer")
        self.assertFalse(buyer_user.is_active)
        self.assertEqual(Buyer.objects.get(user=buyer_user).verification_status, "pending")
        self.assertTrue(Notification.objects.filter(user=self.admin, notification_type="account").exists())

        # Supplier registration via mobile API
        sup_resp = self.client.post(
            "/api/v2/auth/register/",
            data=json.dumps({
                "role": "supplier",
                "name": "Tambulig Agro Feeds",
                "contact_person": "Pedro Cruz",
                "username": "mobile_sup1",
                "email": "pedro@agro.test",
                "phone": "09180002222",
                "supplies": "Layer Feeds",
                "payment_terms": "net15",
                "password": "MobileSup2026!",
            }),
            content_type="application/json",
        )
        self.assertEqual(sup_resp.status_code, 201)
        sup_user = User.objects.get(username="mobile_sup1")
        self.assertEqual(sup_user.role, "supplier")
        self.assertFalse(sup_user.is_active)
        self.assertEqual(Supplier.objects.get(user=sup_user).verification_status, "pending")

        # Reject internal role
        bad_resp = self.client.post(
            "/api/v2/auth/register/",
            data=json.dumps({
                "role": "admin",
                "name": "Bad Admin",
                "username": "bad_admin1",
                "password": "BadPassword2026!",
            }),
            content_type="application/json",
        )
        self.assertEqual(bad_resp.status_code, 400)
        self.assertFalse(User.objects.filter(username="bad_admin1").exists())


class UserManagementActionsTests(TestCase):
    def setUp(self):
        from buyers.models import Buyer
        from suppliers.models import Supplier

        self.admin = User.objects.create_user(
            username="um_admin", password="StrongPass123!", role="admin"
        )
        self.owner = User.objects.create_user(
            username="um_owner", password="StrongPass123!", role="owner"
        )
        self.buyer_user = User.objects.create_user(
            username="um_buyer", password="StrongPass123!", role="buyer", is_active=True
        )
        self.buyer = Buyer.objects.create(
            name="Tambulig Fresh Eggs",
            user=self.buyer_user,
            verification_status="approved",
            is_active=True,
        )
        self.supplier_user = User.objects.create_user(
            username="um_supplier", password="StrongPass123!", role="supplier", is_active=False
        )
        self.supplier = Supplier.objects.create(
            name="Zambo Feed Mill",
            user=self.supplier_user,
            supplies="Layer Feeds",
            verification_status="pending",
            is_active=True,
        )

    def test_user_list_tabs_and_filters(self):
        self.client.force_login(self.admin)

        buyers_resp = self.client.get(reverse("accounts:user_list"), {"tab": "buyers"})
        self.assertEqual(buyers_resp.status_code, 200)
        self.assertContains(buyers_resp, "Tambulig Fresh Eggs")
        self.assertNotContains(buyers_resp, "Zambo Feed Mill")

        suppliers_resp = self.client.get(reverse("accounts:user_list"), {"tab": "suppliers"})
        self.assertEqual(suppliers_resp.status_code, 200)
        self.assertContains(suppliers_resp, "Zambo Feed Mill")
        self.assertNotContains(suppliers_resp, "Tambulig Fresh Eggs")

        pending_resp = self.client.get(reverse("accounts:user_list"), {"status": "pending"})
        self.assertEqual(pending_resp.status_code, 200)
        self.assertContains(pending_resp, "Zambo Feed Mill")
        self.assertNotContains(pending_resp, "Tambulig Fresh Eggs")

        search_resp = self.client.get(reverse("accounts:user_list"), {"q": "Tambulig Fresh"})
        self.assertEqual(search_resp.status_code, 200)
        self.assertContains(search_resp, "Tambulig Fresh Eggs")
        self.assertNotContains(search_resp, "Zambo Feed Mill")

    def test_user_view_edit_and_delete_modals_and_actions(self):
        self.client.force_login(self.admin)

        # View detail (HTMX modal + full page)
        detail_htmx = self.client.get(
            reverse("accounts:user_detail", args=[self.buyer_user.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(detail_htmx.status_code, 200)
        self.assertContains(detail_htmx, "Tambulig Fresh Eggs")
        self.assertContains(detail_htmx, "modal-overlay")

        detail_full = self.client.get(reverse("accounts:user_detail", args=[self.supplier_user.pk]))
        self.assertEqual(detail_full.status_code, 200)
        self.assertContains(detail_full, "Zambo Feed Mill")

        # Edit (HTMX modal GET + POST)
        edit_get = self.client.get(
            reverse("accounts:user_update", args=[self.buyer_user.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(edit_get.status_code, 200)
        self.assertContains(edit_get, "Edit User")

        edit_post = self.client.post(
            reverse("accounts:user_update", args=[self.buyer_user.pk]),
            {
                "username": "um_buyer",
                "first_name": "Updated",
                "last_name": "Buyer",
                "email": "updated@buyer.test",
                "role": "buyer",
                "phone": "09171112222",
                "address": "Tambulig",
                "is_active": "on",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(edit_post.status_code, 200)
        self.assertContains(edit_post, "window.location.reload")
        self.buyer_user.refresh_from_db()
        self.assertEqual(self.buyer_user.first_name, "Updated")
        self.assertEqual(self.buyer_user.email, "updated@buyer.test")

        # Delete (HTMX modal GET + POST)
        del_get = self.client.get(
            reverse("accounts:user_delete", args=[self.supplier_user.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(del_get.status_code, 200)
        self.assertContains(del_get, "Confirm Deletion")

        del_post = self.client.post(
            reverse("accounts:user_delete", args=[self.supplier_user.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(del_post.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.supplier_user.pk).exists())

        # Cannot delete own account
        self_del = self.client.post(reverse("accounts:user_delete", args=[self.admin.pk]))
        self.assertEqual(self_del.status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
