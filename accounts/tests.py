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