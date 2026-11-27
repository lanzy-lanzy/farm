from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from dashboard.models import FarmProfile

User = get_user_model()


class FarmSettingsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="settings_admin", password="StrongPass123!", role="admin"
        )

    def test_farm_profile_settings_get_and_post(self):
        self.client.force_login(self.admin)

        get_resp = self.client.get(reverse("settings_app:farm_settings"))
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, "Farm Profile")
        self.assertContains(get_resp, "Tambulig Poultry Farm")

        post_resp = self.client.post(
            reverse("settings_app:farm_settings"),
            {
                "farm_name": "Tambulig Poultry Farm Main",
                "location": "Tambulig, Zamboanga del Sur",
                "farm_size": "3 hectares",
                "farm_type": "layer",
                "contact_number": "09171234567",
                "email": "admin@tambuligfarm.test",
            },
            follow=True,
        )
        self.assertEqual(post_resp.status_code, 200)
        profile = FarmProfile.objects.get(user=self.admin)
        self.assertEqual(profile.farm_name, "Tambulig Poultry Farm Main")
        self.assertEqual(profile.farm_type, "layer")
        self.assertEqual(profile.contact_number, "09171234567")
