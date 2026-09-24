from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.models import User
from dashboard.models import FarmProfile
from flocks.models import FlockBatch
from inventory.models import InventoryItem, InventoryCategory, Unit
from feeding.models import FeedingRecord
from medicine.models import MedicineRecord
from eggs.models import EggProduction
from mortality.models import MortalityRecord
from sales.models import SalesRecord
from expenses.models import ExpenseRecord, ExpenseCategory
from suppliers.models import Supplier
from buyers.models import Buyer


class Command(BaseCommand):
    help = "Seed database with sample data"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding database...")

        # Create users
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@farm.com",
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_user.set_password("admin123")
        admin_user.save()

        owner_user, _ = User.objects.get_or_create(
            username="owner",
            defaults={
                "email": "owner@farm.com",
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "role": "owner",
            },
        )
        owner_user.set_password("owner123")
        owner_user.save()

        staff_user, _ = User.objects.get_or_create(
            username="staff",
            defaults={
                "email": "staff@farm.com",
                "first_name": "Pedro",
                "last_name": "Santos",
                "role": "staff",
            },
        )
        staff_user.set_password("staff123")
        staff_user.save()

        # Create farm profile
        FarmProfile.objects.get_or_create(
            user=owner_user,
            defaults={
                "farm_name": "Tambulig Poultry Farm",
                "location": "Tambulig, Zamboanga del Sur",
                "farm_type": "mixed",
                "contact_number": "+63 912 345 6789",
            },
        )

        # Create units
        units = {}
        for name, abbr in [("Kilogram", "kg"), ("Gram", "g"), ("Piece", "pc"), ("Sack", "sack"), ("Liter", "L"), ("Bottle", "btl")]:
            unit, _ = Unit.objects.get_or_create(name=name, defaults={"abbreviation": abbr})
            units[abbr] = unit

        # Create categories
        categories = {}
        for name in ["Feeds", "Medicine", "Vaccine", "Vitamin", "Equipment", "Supplies"]:
            cat, _ = InventoryCategory.objects.get_or_create(name=name)
            categories[name] = cat

        # Create suppliers
        supplier1, _ = Supplier.objects.get_or_create(
            name="Zamboanga Feeds Supplier",
            defaults={"contact_person": "Maria Garcia", "phone": "+63 911 123 4567", "supplies": "Poultry Feeds"},
        )
        supplier2, _ = Supplier.objects.get_or_create(
            name="Vet Med Supply",
            defaults={"contact_person": "Dr. Reyes", "phone": "+63 922 234 5678", "supplies": "Medicines and Vaccines"},
        )

        # Supplier portal demo login -> redirects to /portal/ (external role)
        supplier_user, _ = User.objects.get_or_create(
            username="supplier",
            defaults={
                "email": "supplier@farm.com",
                "first_name": "Maria",
                "last_name": "Garcia",
                "role": "supplier",
            },
        )
        supplier_user.set_password("supplier123")
        supplier_user.save()
        supplier1.user = supplier_user
        supplier1.verification_status = "approved"
        supplier1.verified_by = admin_user
        supplier1.verified_at = timezone.now()
        supplier1.save()

        # Create inventory items
        InventoryItem.objects.get_or_create(
            name="Chick Starter Crumbs",
            defaults={
                "category": categories["Feeds"],
                "quantity": Decimal("500"),
                "unit": units["kg"],
                "supplier": supplier1,
                "cost_per_unit": Decimal("45.00"),
                "reorder_level": Decimal("100"),
                "created_by": admin_user,
            },
        )
        InventoryItem.objects.get_or_create(
            name="Grower Pellets",
            defaults={
                "category": categories["Feeds"],
                "quantity": Decimal("300"),
                "unit": units["kg"],
                "supplier": supplier1,
                "cost_per_unit": Decimal("42.00"),
                "reorder_level": Decimal("80"),
                "created_by": admin_user,
            },
        )
        InventoryItem.objects.get_or_create(
            name="Layer Mash",
            defaults={
                "category": categories["Feeds"],
                "quantity": Decimal("400"),
                "unit": units["kg"],
                "supplier": supplier1,
                "cost_per_unit": Decimal("40.00"),
                "reorder_level": Decimal("100"),
                "created_by": admin_user,
            },
        )
        InventoryItem.objects.get_or_create(
            name="Antibiotic Solution",
            defaults={
                "category": categories["Medicine"],
                "quantity": Decimal("50"),
                "unit": units["btl"],
                "supplier": supplier2,
                "cost_per_unit": Decimal("120.00"),
                "reorder_level": Decimal("10"),
                "created_by": admin_user,
            },
        )
        InventoryItem.objects.get_or_create(
            name="Newcastle Disease Vaccine",
            defaults={
                "category": categories["Vaccine"],
                "quantity": Decimal("100"),
                "unit": units["pc"],
                "supplier": supplier2,
                "cost_per_unit": Decimal("25.00"),
                "reorder_level": Decimal("20"),
                "created_by": admin_user,
            },
        )

        # Create flock batches
        today = timezone.now().date()
        batch1, _ = FlockBatch.objects.get_or_create(
            batch_number="BATCH-2024-001",
            defaults={
                "breed": "Rhode Island Red",
                "quantity": 500,
                "current_quantity": 485,
                "age_days": 120,
                "source": "Local Hatchery",
                "date_acquired": today - timedelta(days=120),
                "growing_stage": "layer",
                "status": "active",
                "created_by": owner_user,
            },
        )
        batch2, _ = FlockBatch.objects.get_or_create(
            batch_number="BATCH-2024-002",
            defaults={
                "breed": "Broiler Classic",
                "quantity": 300,
                "current_quantity": 290,
                "age_days": 45,
                "source": "Poultry Center",
                "date_acquired": today - timedelta(days=45),
                "growing_stage": "grower",
                "status": "active",
                "created_by": owner_user,
            },
        )

        # Create feeding records
        for i in range(7):
            date = today - timedelta(days=i)
            feed_item = InventoryItem.objects.get(name="Layer Mash")
            FeedingRecord.objects.get_or_create(
                flock=batch1,
                feed_item=feed_item,
                feeding_date=date,
                defaults={
                    "quantity_used": Decimal("25"),
                    "recorded_by": staff_user,
                },
            )

        # Create egg production
        for i in range(7):
            date = today - timedelta(days=i)
            EggProduction.objects.get_or_create(
                flock=batch1,
                production_date=date,
                defaults={
                    "good_eggs": 420,
                    "cracked_eggs": 15,
                    "rejected_eggs": 5,
                    "recorded_by": staff_user,
                },
            )

        # Create expense categories
        exp_cats = {}
        for name in ["Feeds", "Medicine", "Labor", "Transportation", "Utilities", "Maintenance"]:
            cat, _ = ExpenseCategory.objects.get_or_create(name=name)
            exp_cats[name] = cat

        # Create expense records
        ExpenseRecord.objects.get_or_create(
            category=exp_cats["Feeds"],
            description="Monthly feeds purchase",
            defaults={
                "amount": Decimal("25000.00"),
                "expense_date": today - timedelta(days=5),
                "payment_method": "cash",
                "recorded_by": owner_user,
            },
        )

        # Create buyers
        buyer_account, _ = Buyer.objects.get_or_create(
            name="Tambulig Market",
            defaults={"buyer_type": "wholesale", "phone": "+63 933 345 6789"},
        )

        # Buyer portal demo login -> redirects to /portal/ (external role)
        buyer_user, _ = User.objects.get_or_create(
            username="buyer",
            defaults={
                "email": "buyer@farm.com",
                "first_name": "Tambulig",
                "last_name": "Market",
                "role": "buyer",
            },
        )
        buyer_user.set_password("buyer123")
        buyer_user.save()
        buyer_account.user = buyer_user
        buyer_account.verification_status = "approved"
        buyer_account.verified_by = admin_user
        buyer_account.verified_at = timezone.now()
        buyer_account.save()

        # Create sales
        SalesRecord.objects.get_or_create(
            product_name="Eggs - Good",
            defaults={
                "product_type": "eggs",
                "flock": batch1,
                "quantity": Decimal("500"),
                "unit_price": Decimal("8.50"),
                "date_sold": today - timedelta(days=1),
                "payment_status": "paid",
                "amount_paid": Decimal("4250.00"),
                "recorded_by": owner_user,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Database seeded successfully!\n"
                "Demo logins (change before real use):\n"
                "  admin    / admin123     (Administrator)\n"
                "  owner    / owner123     (Farm Owner)\n"
                "  staff    / staff123     (Staff/Caretaker)\n"
                "  buyer    / buyer123     (Buyer portal)\n"
                "  supplier / supplier123  (Supplier portal)"
            )
        )
