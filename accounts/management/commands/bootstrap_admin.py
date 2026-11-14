"""Create the initial admin user on first boot (fresh production database).

Runs on every startup via startup.sh but does nothing once any user exists.
Credentials come from environment variables so no secrets live in the repo:

    ADMIN_USERNAME, ADMIN_PASSWORD  (required to bootstrap)
    ADMIN_EMAIL, ADMIN_FIRST_NAME, ADMIN_LAST_NAME  (optional)
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial admin user from ADMIN_USERNAME/ADMIN_PASSWORD if the user table is empty."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.exists():
            self.stdout.write("Users already exist; skipping admin bootstrap.")
            return

        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")
        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "No users found and ADMIN_USERNAME/ADMIN_PASSWORD are not set; "
                    "skipping admin bootstrap."
                )
            )
            return

        user = User.objects.create_superuser(
            username=username,
            email=os.environ.get("ADMIN_EMAIL", ""),
            password=password,
        )
        user.role = "admin"
        user.first_name = os.environ.get("ADMIN_FIRST_NAME", "Farm")
        user.last_name = os.environ.get("ADMIN_LAST_NAME", "Admin")
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))