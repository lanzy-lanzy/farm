"""Seed default farm products (including egg sizes) with permanent static images.

Runs automatically on every deployment boot via startup.sh so redeploys on
ephemeral storage always have the full farm catalog and product photos ready.
Idempotent: existing products keep any admin-edited prices or active flags,
while missing products or blank static_image paths are restored cleanly.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from sales.models import Product

SEED_PRODUCTS = [
    # Eggs by size
    {
        "name": "Small Eggs (Tray)",
        "product_type": "eggs",
        "unit_label": "tray",
        "unit_price": Decimal("165.00"),
        "static_image": "images/products/eggs_small.jpg",
    },
    {
        "name": "Medium Eggs (Tray)",
        "product_type": "eggs",
        "unit_label": "tray",
        "unit_price": Decimal("190.00"),
        "static_image": "images/products/eggs_medium.jpg",
    },
    {
        "name": "Large Eggs (Tray)",
        "product_type": "eggs",
        "unit_label": "tray",
        "unit_price": Decimal("210.00"),
        "static_image": "images/products/eggs_large.jpg",
    },
    {
        "name": "Extra Large Eggs (Tray)",
        "product_type": "eggs",
        "unit_label": "tray",
        "unit_price": Decimal("230.00"),
        "static_image": "images/products/eggs_xl.jpg",
    },
    {
        "name": "Jumbo Eggs (Tray)",
        "product_type": "eggs",
        "unit_label": "tray",
        "unit_price": Decimal("250.00"),
        "static_image": "images/products/eggs_xl.jpg",
    },
    # Poultry & farm by-products
    {
        "name": "Live Broiler Chicken",
        "product_type": "chicken",
        "unit_label": "head",
        "unit_price": Decimal("220.00"),
        "static_image": "images/products/live_chicken.jpg",
    },
    {
        "name": "Dressed Whole Chicken",
        "product_type": "dressed",
        "unit_label": "kg",
        "unit_price": Decimal("195.00"),
        "static_image": "images/products/dressed_chicken.jpg",
    },
    {
        "name": "Organic Poultry Manure",
        "product_type": "manure",
        "unit_label": "sack",
        "unit_price": Decimal("65.00"),
        "static_image": "images/products/organic_manure.jpg",
    },
]


class Command(BaseCommand):
    help = "Seed default farm products and egg sizes with bundled static images."

    def handle(self, *args, **options):
        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).first()

        created_count = 0
        updated_count = 0
        for item in SEED_PRODUCTS:
            existing = Product.objects.filter(name__iexact=item["name"]).first()
            if existing is None:
                Product.objects.create(
                    name=item["name"],
                    product_type=item["product_type"],
                    unit_label=item["unit_label"],
                    unit_price=item["unit_price"],
                    static_image=item["static_image"],
                    is_active=True,
                    created_by=admin,
                )
                created_count += 1
            elif not existing.static_image:
                existing.static_image = item["static_image"]
                existing.save(update_fields=["static_image"])
                updated_count += 1

        # Backfill any admin-created products that don't yet have a static fallback image.
        for prod in Product.objects.filter(static_image=""):
            prod.static_image = prod.default_static_path()
            prod.save(update_fields=["static_image"])
            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Products seeded: {created_count} created, {updated_count} image paths synced "
                f"({Product.objects.count()} total)."
            )
        )
