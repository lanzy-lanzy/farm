from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Notification, ActivityLog

User = get_user_model()


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.notification = Notification.objects.create(
            user=self.user,
            notification_type="low_stock",
            title="Low Stock Alert",
            message="Item is running low",
        )

    def test_notification_creation(self):
        self.assertEqual(Notification.objects.count(), 1)

    def test_default_is_read(self):
        self.assertFalse(self.notification.is_read)

    def test_mark_as_read(self):
        self.notification.mark_as_read()
        self.assertTrue(self.notification.is_read)

    def test_str_representation(self):
        self.assertEqual(str(self.notification), "Low Stock Alert - admin")


class ActivityLogModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.log = ActivityLog.objects.create(
            user=self.user,
            action="create",
            model_name="FlockBatch",
            object_repr="B001",
        )

    def test_activity_log_creation(self):
        self.assertEqual(ActivityLog.objects.count(), 1)

    def test_str_representation(self):
        self.assertIn("Created", str(self.log))
        self.assertIn("Created", str(self.log))


class NotificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="admin123", role="admin")
        self.client.force_login(self.user)
        Notification.objects.create(
            user=self.user,
            notification_type="activity",
            title="Test Notification",
            message="Test message",
        )

    def test_notification_list_view(self):
        response = self.client.get(reverse("notifications:notification_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Notification")

    def test_mark_as_read_view(self):
        notification = Notification.objects.first()
        response = self.client.get(
            reverse("notifications:notification_mark_read", args=[notification.pk])
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_activity_log_view(self):
        ActivityLog.objects.create(
            user=self.user,
            action="create",
            model_name="Test",
            object_repr="TestObj",
        )
        response = self.client.get(reverse("notifications:activity_log"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TestObj")


class InboxModalCrudTests(TestCase):
    """The internal inbox: a row leads to the page that handles it, CRUD runs in modals."""

    def setUp(self):
        self.staff = User.objects.create_user(username="carey", password="pass12345", role="staff")
        self.owner = User.objects.create_user(username="rita", password="pass12345", role="owner")
        self.client.force_login(self.staff)

    def _notice(self, user=None, **kwargs):
        kwargs.setdefault("notification_type", "low_stock")
        kwargs.setdefault("title", "Low Stock: Layer feed")
        kwargs.setdefault("message", "2 bags left in the store.")
        return Notification.objects.create(user=user or self.staff, **kwargs)

    def _table(self, html):
        """The inbox table alone, so assertions ignore the top-bar bell dropdown."""
        return html[html.index("<table"): html.index("</table>")]

    def test_inbox_is_one_table_with_modal_actions(self):
        notice = self._notice(link="/inventory/")
        response = self.client.get(reverse("notifications:notification_list"))
        html = response.content.decode()
        table = self._table(html)
        self.assertIn("<table", table)
        self.assertIn('hx-target="#modal-container"', table)
        # Nothing is pre-opened: dialogs arrive over HTMX.
        self.assertNotIn('id="modal-overlay"', html)
        # Both the title and the Process shortcut run the mark-read redirect.
        self.assertEqual(table.count(reverse("notifications:notification_mark_read", args=[notice.pk])), 2)
        self.assertIn("Process", table)

    def test_clicking_a_notification_lands_on_the_page_that_handles_it(self):
        notice = self._notice(link="/inventory/")
        response = self.client.get(reverse("notifications:notification_mark_read", args=[notice.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/inventory/")
        notice.refresh_from_db()
        self.assertTrue(notice.is_read)

    def test_an_off_site_link_is_never_followed(self):
        # Saved straight through the ORM, so this is a row an old import could have left behind.
        notice = self._notice(link="https://evil.example/phish")
        response = self.client.get(reverse("notifications:notification_mark_read", args=[notice.pk]))
        self.assertRedirects(response, reverse("notifications:notification_list"))

    def test_marking_a_link_less_notice_read_over_htmx_refreshes_the_inbox(self):
        notice = self._notice()
        response = self.client.post(
            reverse("notifications:notification_mark_read", args=[notice.pk]),
            headers={"hx-request": "true"},
        )
        self.assertContains(response, "modal-overlay")
        notice.refresh_from_db()
        self.assertTrue(notice.is_read)

    def test_compose_arrives_as_a_modal_fragment(self):
        response = self.client.get(
            reverse("notifications:notification_create"), headers={"hx-request": "true"}
        )
        self.assertContains(response, 'id="modal-overlay"')
        self.assertNotContains(response, "<!DOCTYPE html")
        self.assertContains(response, "The whole farm team")

    def test_compose_starts_on_a_real_subject_so_send_is_not_blocked(self):
        # A required select parked on its empty "---------" option stops the browser
        # submitting at all, with nothing on screen to explain why.
        response = self.client.get(
            reverse("notifications:notification_create"), headers={"hx-request": "true"}
        )
        select = response.content.decode().split('<select name="notification_type')[1]
        select = select[: select.index("</select>")]
        self.assertNotIn('<option value=""', select)
        self.assertIn('value="activity" selected', select)

    def test_plain_get_on_compose_falls_back_to_the_inbox(self):
        response = self.client.get(reverse("notifications:notification_create"))
        self.assertRedirects(response, reverse("notifications:notification_list"))

    def test_compose_for_the_team_reaches_every_internal_inbox(self):
        response = self.client.post(
            reverse("notifications:notification_create"),
            {
                "notification_type": "activity",
                "title": "Disinfect house 3",
                "message": "Thursday morning before feeding.",
                "link": "/flocks/",
                "audience": "team",
            },
            headers={"hx-request": "true"},
        )
        self.assertContains(response, "modal-overlay")
        for user in (self.staff, self.owner):
            self.assertTrue(
                user.notifications.filter(title="Disinfect house 3", link="/flocks/").exists()
            )

    def test_compose_can_stay_a_private_reminder(self):
        self.client.post(
            reverse("notifications:notification_create"),
            {
                "notification_type": "vaccination",
                "title": "Weigh the pullets",
                "message": "Every second Tuesday.",
                "link": "",
                "audience": "me",
            },
            headers={"hx-request": "true"},
        )
        self.assertTrue(self.staff.notifications.filter(title="Weigh the pullets").exists())
        self.assertEqual(self.owner.notifications.count(), 0)

    def test_a_link_leaving_the_app_is_refused_by_the_form(self):
        response = self.client.post(
            reverse("notifications:notification_create"),
            {
                "notification_type": "activity",
                "title": "Look at this",
                "message": "Click through",
                "link": "http://evil.example/",
                "audience": "me",
            },
            headers={"hx-request": "true"},
        )
        self.assertContains(response, "in-app path")
        self.assertFalse(self.staff.notifications.exists())

    def test_inbox_actions_only_see_your_own_copy(self):
        foreign = Notification.objects.create(
            user=self.owner, notification_type="activity", title="Owner note", message="Not yours"
        )
        for url_name in (
            "notification_detail",
            "notification_update",
            "notification_delete",
            "notification_mark_unread",
        ):
            url = reverse(f"notifications:{url_name}", args=[foreign.pk])
            response = self.client.post(url, headers={"hx-request": "true"})
            self.assertEqual(response.status_code, 404, url)
        self.assertTrue(Notification.objects.filter(pk=foreign.pk).exists())

    def test_portal_users_are_kept_out_of_inbox_management(self):
        buyer = User.objects.create_user(username="buyer1", password="pass12345", role="buyer")
        self.client.force_login(buyer)
        response = self.client.get(
            reverse("notifications:notification_create"), headers={"hx-request": "true"}
        )
        self.assertEqual(response.status_code, 403)

    def test_edit_modal_opens_prefilled_and_keeps_the_recipient(self):
        notice = self._notice(title="Wrong title", link="/inventory/")
        edit_url = reverse("notifications:notification_update", args=[notice.pk])
        response = self.client.get(edit_url, headers={"hx-request": "true"})
        self.assertContains(response, 'value="Wrong title"')
        self.assertContains(response, edit_url)
        self.client.post(
            edit_url,
            {
                "notification_type": "low_stock",
                "title": "Layer feed low",
                "message": "2 bags left.",
                "link": "/inventory/",
            },
            headers={"hx-request": "true"},
        )
        notice.refresh_from_db()
        self.assertEqual(notice.title, "Layer feed low")
        self.assertEqual(notice.user_id, self.staff.pk)

    def test_dismissing_removes_only_that_row(self):
        mine = self._notice(title="Mine")
        theirs = Notification.objects.create(
            user=self.owner, notification_type="activity", title="Theirs", message="Keep"
        )
        response = self.client.post(
            reverse("notifications:notification_delete", args=[mine.pk]),
            headers={"hx-request": "true"},
        )
        self.assertContains(response, "modal-overlay")
        self.assertFalse(Notification.objects.filter(pk=mine.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=theirs.pk).exists())

    def test_mark_all_read_clears_the_inbox(self):
        self._notice(title="Fresh one")
        self._notice(title="Fresh two")
        response = self.client.post(
            reverse("notifications:notification_mark_all_read"), headers={"hx-request": "true"}
        )
        self.assertContains(response, "modal-overlay")
        self.assertEqual(self.staff.notifications.filter(is_read=False).count(), 0)

    def test_unread_filter_shows_only_what_is_left(self):
        self._notice(title="Already looked at", is_read=True)
        self._notice(title="Still waiting")
        response = self.client.get(reverse("notifications:notification_list"), {"filter": "unread"})
        table = self._table(response.content.decode())
        self.assertIn("Still waiting", table)
        self.assertNotIn("Already looked at", table)

    def test_bell_dropdown_offers_the_latest_alerts(self):
        self._notice(title="Feed running low", link="/inventory/")
        response = self.client.get(reverse("notifications:notification_list"))
        self.assertContains(response, "Latest notifications")
        self.assertContains(response, "Feed running low")
        self.assertContains(response, "opens the page to handle it")

