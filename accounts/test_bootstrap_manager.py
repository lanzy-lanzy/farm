import os
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.test import TestCase

class BootstrapManagerTests(TestCase):
    def bootstrap(self, password="test-manager-password"):
        with patch.dict(os.environ, {"MANAGER_USERNAME": "testmanager", "MANAGER_PASSWORD": password}, clear=True):
            call_command("bootstrap_admin", stdout=StringIO(), stderr=StringIO())

    def test_creates_authenticating_staff_and_is_repeatable(self):
        self.bootstrap()
        self.bootstrap()
        user = authenticate(username="testmanager", password="test-manager-password")
        self.assertIsNotNone(user)
        self.assertEqual(user.role, "staff")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertEqual(get_user_model().objects.filter(username="testmanager").count(), 1)

    def test_resyncs_password_and_reactivates_staff(self):
        get_user_model().objects.create_user(username="testmanager", password="old-password", role="staff", is_active=False)
        self.bootstrap("replacement-test-password")
        self.assertIsNotNone(authenticate(username="testmanager", password="replacement-test-password"))

    def test_does_not_overwrite_other_role(self):
        user = get_user_model().objects.create_user(username="testmanager", password="original-password", role="admin")
        self.bootstrap()
        user.refresh_from_db()
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.check_password("original-password"))
