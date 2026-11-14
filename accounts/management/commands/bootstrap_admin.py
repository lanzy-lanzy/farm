"""Ensure the farm's core login accounts exist on every boot.

Runs on every startup via startup.sh. Credentials come only from environment
variables, so no secrets live in this (public) repo. The environment is the
source of truth: if the database was reset, or a password drifted, the accounts
are recreated / re-synced to the values below.

    ADMIN_USERNAME, ADMIN_PASSWORD        admin superuser
    ADMIN_EMAIL, ADMIN_FIRST_NAME, ADMIN_LAST_NAME  (optional)
    BUYER_USERNAME, BUYER_PASSWORD        buyer portal login
    BUYER_CONTACT                         contact it links to (default "Manila Egg Traders")
    SUPPLIER_USERNAME, SUPPLIER_PASSWORD  supplier portal login
    SUPPLIER_CONTACT                      contact it links to (default "Agrivet Feed Supply")

Any pair left unset is skipped, so the command is safe to run anywhere.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from buyers.models import Buyer
from suppliers.models import Supplier

PORTAL_ACCOUNTS = [
    # role, env prefix, contact model, default contact name
    ("buyer", "BUYER", Buyer, "Manila Egg Traders"),
    ("supplier", "SUPPLIER", Supplier, "Agrivet Feed Supply"),
]


class Command(BaseCommand):
    help = "Create or re-sync the admin and portal accounts from environment variables."

    def handle(self, *args, **options):
        admin = self.sync_admin()
        for role, prefix, model, default_contact in PORTAL_ACCOUNTS:
            self.sync_portal_account(role, prefix, model, default_contact, admin)

    def sync_admin(self):
        User = get_user_model()
        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")
        if not username or not password:
            self.stdout.write(
                self.style.WARNING("ADMIN_USERNAME/ADMIN_PASSWORD not set; skipping admin.")
            )
            return User.objects.filter(is_superuser=True).first()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": os.environ.get("ADMIN_EMAIL", ""),
                "first_name": os.environ.get("ADMIN_FIRST_NAME", "Farm"),
                "last_name": os.environ.get("ADMIN_LAST_NAME", "Admin"),
            },
        )
        changed = self.apply_credentials(user, password)
        if not (user.is_staff and user.is_superuser and user.role == "admin"):
            user.is_staff = user.is_superuser = True
            user.role = "admin"
            changed = True
        if changed or created:
            user.save()
        self.report("admin", username, created, changed)
        return user

    def sync_portal_account(self, role, prefix, model, default_contact, operator):
        User = get_user_model()
        username = os.environ.get(f"{prefix}_USERNAME")
        password = os.environ.get(f"{prefix}_PASSWORD")
        if not username or not password:
            return

        contact_name = os.environ.get(f"{prefix}_CONTACT", default_contact)
        contact, _ = model.objects.get_or_create(name=contact_name)

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"role": role, "first_name": contact_name[:30], "email": contact.email or ""},
        )
        changed = self.apply_credentials(user, password)
        if user.role != role:
            user.role = role
            changed = True
        if changed or created:
            user.save()

        # Link the login to its contact and keep the contact approved and active.
        if contact.user_id != user.pk or contact.verification_status != "approved" or not contact.is_active:
            model.objects.filter(user=user).exclude(pk=contact.pk).update(user=None)
            contact.user = user
            contact.is_active = True
            if contact.verification_status != "approved":
                contact.verification_status = "approved"
                contact.rejection_reason = None
                contact.verified_by = operator
                contact.verified_at = timezone.now()
            contact.save()
            changed = True
        self.report(role, username, created, changed)

    @staticmethod
    def apply_credentials(user, password):
        changed = False
        if not user.is_active:
            user.is_active = True
            changed = True
        if not user.has_usable_password() or not user.check_password(password):
            user.set_password(password)
            changed = True
        return changed

    def report(self, label, username, created, changed):
        if created:
            msg = f"Created {label} account '{username}'."
        elif changed:
            msg = f"Re-synced {label} account '{username}' from environment."
        else:
            msg = f"{label.capitalize()} account '{username}' already in sync."
        self.stdout.write(self.style.SUCCESS(msg))
