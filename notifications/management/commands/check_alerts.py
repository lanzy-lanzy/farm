from django.core.management.base import BaseCommand
from notifications.utils import check_and_notify_vaccinations
from inventory.models import InventoryItem
from notifications.utils import check_and_notify_inventory


class Command(BaseCommand):
    help = "Check for low stock, expired items, and upcoming vaccinations"

    def handle(self, *args, **options):
        self.stdout.write("Checking inventory alerts...")
        items = InventoryItem.objects.filter(is_active=True)
        for item in items:
            check_and_notify_inventory(item)
        self.stdout.write(self.style.SUCCESS(f"Checked {items.count()} inventory items."))

        self.stdout.write("Checking vaccination alerts...")
        check_and_notify_vaccinations()
        self.stdout.write(self.style.SUCCESS("Vaccination check complete."))
