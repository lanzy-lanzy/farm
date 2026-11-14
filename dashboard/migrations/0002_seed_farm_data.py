"""Seed a modest, realistic starter dataset (about five rows per model).

Runs automatically on deploy: startup.sh executes ``migrate`` against the fresh
/data SQLite database, so production gets the same starter data as a new local
install. The seed is skipped whenever any flock batch already exists, which
keeps it idempotent and never touches databases that already hold real records.

No users or passwords are created here; the admin account comes from
``bootstrap_admin`` and portal accounts are provisioned separately.
"""

from datetime import time
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

BATCH_NUMBERS = [f"FB-2026-{i:03d}" for i in range(1, 6)]
EXPENSE_DESCRIPTIONS = [
    "Layer mash delivery - 20 sacks",
    "Multivitamins and electrolytes",
    "Caretaker weekly wage",
    "Electricity bill - brooder lamps",
    "Egg trays and packaging",
    "Water line repair",
]
PRODUCT_NAMES = [
    "Fresh Eggs (tray)",
    "Live Chicken",
    "Dressed Chicken",
    "Organic Manure (sack)",
    "Cull Layer",
]
BUYER_NAMES = [
    "Manila Egg Traders",
    "Pagadian Public Market",
    "Zamboanga Grocery Chain",
    "Tambulig Restaurant",
    "Dipolog Farmers Cooperative",
]
SUPPLIER_NAMES = [
    "Agrivet Feed Supply",
    "Zamboanga Vet Pharma",
    "Mindanao Grain Trading",
    "Pacific Packaging Hub",
    "Davao Agri Equipment",
]
DELIVERY_DESCRIPTIONS = [
    "Layer mash - 20 sacks",
    "Grower pellets - 15 sacks",
    "Multivitamins - 10 bottles",
    "Egg trays - 5 bundles",
    "Newcastle vaccine - 2 boxes",
]


def seed_farm_data(apps, schema_editor):
    FlockBatch = apps.get_model("flocks", "FlockBatch")
    if FlockBatch.objects.exists():
        return  # Real data present; never seed over it.

    InventoryCategory = apps.get_model("inventory", "InventoryCategory")
    Unit = apps.get_model("inventory", "Unit")
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    InventoryTransaction = apps.get_model("inventory", "InventoryTransaction")
    Supplier = apps.get_model("suppliers", "Supplier")
    SupplyItem = apps.get_model("suppliers", "SupplyItem")
    DeliveryNotice = apps.get_model("suppliers", "DeliveryNotice")
    Buyer = apps.get_model("buyers", "Buyer")
    OrderRequest = apps.get_model("buyers", "OrderRequest")
    EggProduction = apps.get_model("eggs", "EggProduction")
    DeathRecord = apps.get_model("deaths", "DeathRecord")
    SalesRecord = apps.get_model("sales", "SalesRecord")
    Product = apps.get_model("sales", "Product")
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")
    ExpenseRecord = apps.get_model("expenses", "ExpenseRecord")
    FeedingRecord = apps.get_model("feeding", "FeedingRecord")
    MedicineRecord = apps.get_model("medicine", "MedicineRecord")

    today = timezone.localdate()

    def days_ago(n):
        return today - timezone.timedelta(days=n)

    # --- Suppliers and buyers (contacts only; portal logins stay separate) ---
    # get_or_create by name: production may already hold portal-linked contacts
    # (e.g. Manila Egg Traders); reuse them instead of creating duplicates.
    supplier_specs = [
        ("Agrivet Feed Supply", "Feeds and grain", "net15"),
        ("Zamboanga Vet Pharma", "Medicines and vaccines", "cod"),
        ("Mindanao Grain Trading", "Corn and soybean meal", "net30"),
        ("Pacific Packaging Hub", "Egg trays and sacks", "cod"),
        ("Davao Agri Equipment", "Farm tools and equipment", "net15"),
    ]
    suppliers = []
    for i, (name, supplies, terms) in enumerate(supplier_specs):
        supplier, _ = Supplier.objects.get_or_create(
            name=name,
            defaults={
                "contact_person": f"Contact {i + 1}",
                "phone": f"+63 917 000 {1000 + i}",
                "supplies": supplies,
                "payment_terms": terms,
                "verification_status": "approved",
                "is_active": True,
            },
        )
        suppliers.append(supplier)

    buyer_specs = [
        ("Manila Egg Traders", "wholesale", "Egg trays, weekly standing order"),
        ("Pagadian Public Market", "retail", "Live and dressed chicken"),
        ("Zamboanga Grocery Chain", "business", "Trayed eggs for retail shelves"),
        ("Tambulig Restaurant", "individual", "Dressed chicken, twice a week"),
        ("Dipolog Farmers Cooperative", "wholesale", "Manure for member farms"),
    ]
    buyers = []
    for i, (name, kind, note) in enumerate(buyer_specs):
        buyer, _ = Buyer.objects.get_or_create(
            name=name,
            defaults={
                "buyer_type": kind,
                "notes": note,
                "phone": f"+63 928 000 {2000 + i}",
                "verification_status": "approved",
                "is_active": True,
            },
        )
        buyers.append(buyer)

    # --- Flocks: three layer batches, two broiler batches ---
    flock_specs = [
        # batch, breed, qty, age_days, stage, acquired_days_ago
        ("FB-2026-001", "Hy-Line Brown", 500, 210, "layer", 210),
        ("FB-2026-002", "Rhode Island Red", 450, 180, "layer", 180),
        ("FB-2026-003", "Lohmann Brown", 300, 150, "layer", 150),
        ("FB-2026-004", "Cobb 500", 400, 35, "broiler", 35),
        ("FB-2026-005", "Ross 308", 350, 21, "broiler", 21),
    ]
    flocks = []
    for number, breed, qty, age, stage, acquired in flock_specs:
        flocks.append(
            FlockBatch.objects.create(
                batch_number=number,
                breed=breed,
                quantity=qty,
                current_quantity=qty,
                age_days=age,
                source="Local hatchery",
                date_acquired=days_ago(acquired),
                growing_stage=stage,
                status="active",
            )
        )
    layers, broilers = flocks[:3], flocks[3:]

    # --- Inventory: categories, units, items, opening stock transactions ---
    categories = {
        name: InventoryCategory.objects.create(name=name)
        for name in ["Feeds", "Medicine", "Vaccine", "Packaging", "Farm Produce"]
    }
    units = {
        abbr: Unit.objects.create(name=name, abbreviation=abbr)
        for name, abbr in [
            ("Kilogram", "kg"),
            ("Sack", "sack"),
            ("Tray", "tray"),
            ("Piece", "pc"),
            ("Bottle", "btl"),
        ]
    }
    item_specs = [
        # name, category, unit, opening qty, cost, reorder, sales mapping, supplier
        ("Layer Mash", "Feeds", "kg", "400", "42.00", "100", None, 0),
        ("Grower Pellets", "Feeds", "kg", "300", "44.00", "80", None, 0),
        ("Multivitamins", "Medicine", "btl", "25", "180.00", "5", None, 1),
        ("Newcastle Vaccine", "Vaccine", "btl", "15", "250.00", "5", None, 1),
        ("Eggs (tray)", "Farm Produce", "tray", "120", "210.00", "20", "eggs", None),
        ("Manure (sack)", "Farm Produce", "sack", "40", "150.00", "10", "manure", None),
    ]
    items = []
    for name, cat, unit, qty, cost, reorder, sales_type, supplier_idx in item_specs:
        item = InventoryItem.objects.create(
            name=name,
            category=categories[cat],
            unit=units[unit],
            quantity=Decimal("0"),
            cost_per_unit=Decimal(cost),
            reorder_level=Decimal(reorder),
            sales_product_type=sales_type,
            supplier=suppliers[supplier_idx] if supplier_idx is not None else None,
            date_purchased=days_ago(10),
            is_active=True,
        )
        # Historical models skip custom save(); apply the stock-in effect here.
        InventoryTransaction.objects.create(
            item=item,
            transaction_type="in",
            quantity=Decimal(qty),
            reference="Opening stock",
            notes="Initial stock delivered to the farm.",
        )
        item.quantity = Decimal(qty)
        item.save(update_fields=["quantity"])
        items.append(item)
    layer_mash, grower_pellets, vitamins, vaccine, egg_stock, manure_stock = items

    # --- Egg production: last six days across the three layer batches ---
    egg_rows = [
        # days_ago, flock index, good, cracked, rejected
        (0, 0, 425, 12, 6),
        (1, 0, 418, 15, 5),
        (2, 1, 372, 10, 4),
        (3, 1, 365, 14, 6),
        (4, 2, 246, 8, 3),
        (5, 2, 252, 9, 4),
    ]
    for ago, idx, good, cracked, rejected in egg_rows:
        EggProduction.objects.create(
            flock=layers[idx],
            production_date=days_ago(ago),
            good_eggs=good,
            cracked_eggs=cracked,
            rejected_eggs=rejected,
            total_eggs=good + cracked + rejected,
        )

    # --- Mortality: five small records; keep flock counts consistent ---
    death_rows = [
        # days_ago, flock index, qty, cause
        (1, 3, 3, "Heat stress"),
        (2, 0, 2, "Prolapse"),
        (3, 4, 4, "Culling of weak chicks"),
        (4, 1, 2, "Respiratory infection"),
        (6, 2, 1, "Unknown"),
    ]
    deaths_per_flock = {}
    for ago, idx, qty, cause in death_rows:
        DeathRecord.objects.create(
            flock=flocks[idx],
            date_recorded=days_ago(ago),
            quantity=qty,
            cause_of_death=cause,
        )
        deaths_per_flock[idx] = deaths_per_flock.get(idx, 0) + qty
    for idx, total in deaths_per_flock.items():
        flock = flocks[idx]
        flock.current_quantity = flock.quantity - total
        flock.save(update_fields=["current_quantity"])

    # --- Sales: six records over the past week, mixed payment states ---
    sales_specs = [
        # days_ago, type, name, qty, price, buyer idx, flock idx, status, paid
        (0, "eggs", "Fresh Eggs (tray)", "30", "210.00", 0, 0, "paid", "6300.00"),
        (1, "chicken", "Live Chicken", "40", "190.00", 1, 3, "paid", "7600.00"),
        (2, "eggs", "Fresh Eggs (tray)", "25", "210.00", 2, 1, "partial", "3000.00"),
        (3, "dressed", "Dressed Chicken", "20", "230.00", 3, 4, "paid", "4600.00"),
        (4, "manure", "Organic Manure (sack)", "15", "150.00", 4, None, "pending", "0.00"),
        (6, "eggs", "Fresh Eggs (tray)", "20", "205.00", 0, 2, "paid", "4100.00"),
    ]
    sales = []
    for ago, ptype, name, qty, price, buyer_idx, flock_idx, status, paid in sales_specs:
        quantity, unit_price = Decimal(qty), Decimal(price)
        sales.append(
            SalesRecord.objects.create(
                product_type=ptype,
                flock=flocks[flock_idx] if flock_idx is not None else None,
                buyer=buyers[buyer_idx],
                product_name=name,
                quantity=quantity,
                unit_price=unit_price,
                total_amount=quantity * unit_price,
                date_sold=days_ago(ago),
                payment_status=status,
                amount_paid=Decimal(paid),
            )
        )

    # --- Buyer catalog: five products offered in the portal ---
    product_specs = [
        ("Fresh Eggs (tray)", "eggs", "tray", "210.00"),
        ("Live Chicken", "chicken", "pc", "190.00"),
        ("Dressed Chicken", "dressed", "pc", "230.00"),
        ("Organic Manure (sack)", "manure", "sack", "150.00"),
        ("Cull Layer", "chicken", "pc", "150.00"),
    ]
    for name, ptype, unit_label, price in product_specs:
        Product.objects.create(
            name=name,
            product_type=ptype,
            unit_label=unit_label,
            unit_price=Decimal(price),
            is_active=True,
        )

    # --- Expenses: five categories, six records ---
    expense_categories = {
        name: ExpenseCategory.objects.create(name=name)
        for name in ["Feeds", "Medicine", "Labor", "Utilities", "Maintenance"]
    }
    expense_specs = [
        # description, category, amount, days_ago, method, supplier idx
        (EXPENSE_DESCRIPTIONS[0], "Feeds", "16800.00", 2, "bank_transfer", 0),
        (EXPENSE_DESCRIPTIONS[1], "Medicine", "2350.00", 4, "cash", 1),
        (EXPENSE_DESCRIPTIONS[2], "Labor", "3500.00", 1, "cash", None),
        (EXPENSE_DESCRIPTIONS[3], "Utilities", "1850.00", 5, "gcash", None),
        (EXPENSE_DESCRIPTIONS[4], "Maintenance", "900.00", 3, "cash", 3),
        (EXPENSE_DESCRIPTIONS[5], "Maintenance", "650.00", 6, "cash", None),
    ]
    for description, cat, amount, ago, method, supplier_idx in expense_specs:
        ExpenseRecord.objects.create(
            category=expense_categories[cat],
            supplier=suppliers[supplier_idx] if supplier_idx is not None else None,
            description=description,
            amount=Decimal(amount),
            expense_date=days_ago(ago),
            payment_method=method,
        )

    # --- Feeding: five recent records (stock already covers the usage) ---
    feeding_specs = [
        (0, 0, layer_mash, "28"),
        (1, 0, layer_mash, "27"),
        (2, 1, layer_mash, "25"),
        (3, 3, grower_pellets, "18"),
        (4, 4, grower_pellets, "15"),
    ]
    for ago, idx, feed_item, qty in feeding_specs:
        FeedingRecord.objects.create(
            flock=flocks[idx],
            feed_item=feed_item,
            quantity_used=Decimal(qty),
            feeding_date=days_ago(ago),
            feeding_time=time(6, 30),
        )

    # --- Medicine: five records, no stock linkage to keep counts simple ---
    medicine_specs = [
        # days_ago, flock idx, type, name, dosage, route
        (1, 3, "vaccine", "Newcastle Disease Vaccine", "1 drop per bird", "water"),
        (2, 0, "vitamin", "Multivitamins + Electrolytes", "5 ml per liter", "water"),
        (3, 4, "vaccine", "Gumboro Vaccine", "1 drop per bird", "oral"),
        (5, 1, "vitamin", "Vitamin B Complex", "2 ml per liter", "water"),
        (6, 2, "medicine", "Amoxicillin Soluble", "1 g per liter", "water"),
    ]
    for ago, idx, mtype, name, dosage, route in medicine_specs:
        MedicineRecord.objects.create(
            flock=flocks[idx],
            medicine_item=None,
            medicine_type=mtype,
            medicine_name=name,
            dosage=dosage,
            quantity_used=Decimal("1"),
            date_administered=days_ago(ago),
            administration_route=route,
        )

    # --- Supplier catalog and delivery pipeline ---
    supply_specs = [
        # name, category, price, unit, supplier idx, farm stock row
        ("Layer Mash", "Feeds", "42.00", "kg", 0, layer_mash),
        ("Grower Pellets", "Feeds", "44.00", "kg", 0, grower_pellets),
        ("Multivitamins", "Medicine", "180.00", "btl", 1, vitamins),
        ("Newcastle Vaccine", "Vaccine", "250.00", "btl", 1, vaccine),
        ("Egg Trays (bundle)", "Packaging", "350.00", "pc", 3, None),
    ]
    supply_items = [
        SupplyItem.objects.create(
            supplier=suppliers[supplier_idx],
            name=name,
            category=cat,
            unit_price=Decimal(price),
            unit=units[unit],
            availability="in_stock",
            inventory_item=stock_row,
            is_active=True,
        )
        for name, cat, price, unit, supplier_idx, stock_row in supply_specs
    ]

    delivery_specs = [
        # days out, status, supply idx, qty, origin
        (2, "announced", 0, "20", "supplier"),
        (1, "confirmed", 1, "15", "supplier"),
        (0, "received", 2, "10", "supplier"),
        (3, "announced", 3, "5", "farm"),
        (-1, "received", 4, "2", "farm"),
    ]
    for offset, status, supply_idx, qty, origin in delivery_specs:
        DeliveryNotice.objects.create(
            supplier=supply_items[supply_idx].supplier,
            origin=origin,
            supply_item=supply_items[supply_idx],
            inventory_item=supply_items[supply_idx].inventory_item,
            description=DELIVERY_DESCRIPTIONS[supply_idx],
            quantity=Decimal(qty),
            expected_date=days_ago(-offset),
            status=status,
        )

    # --- Order requests: one per funnel stage ---
    order_specs = [
        # buyer idx, product idx, qty, price, status, days_ago
        (0, 0, "40", "210.00", "submitted", 0),
        (1, 1, "30", "190.00", "under_review", 1),
        (2, 0, "25", "205.00", "quoted", 2),
        (3, 2, "15", "230.00", "accepted", 3),
        (4, 3, "10", "150.00", "converted", 5),
    ]
    year = today.year
    for seq, (buyer_idx, product_idx, qty, price, status, ago) in enumerate(
        order_specs, start=1
    ):
        product_name, ptype, _, catalog_price = product_specs[product_idx]
        order = OrderRequest.objects.create(
            request_number=f"REQ-{year}-{seq:04d}",
            buyer=buyers[buyer_idx],
            source="portal",
            product_type=ptype,
            product_name=product_name,
            quantity=Decimal(qty),
            requested_unit_price=Decimal(price),
            requested_date=days_ago(ago),
            status=status,
            quoted_unit_price=Decimal(price) if status in ("quoted", "accepted", "converted") else None,
            staff_note="Seeded starter request.",
        )
        if status == "converted":
            order.sales_record = sales[4]
            order.save(update_fields=["sales_record"])


def unseed_farm_data(apps, schema_editor):
    """Reverse helper: remove only the rows this migration created."""
    FlockBatch = apps.get_model("flocks", "FlockBatch")
    if not FlockBatch.objects.filter(batch_number__in=BATCH_NUMBERS).exists():
        return
    for app_label, model_name, filters in [
        ("buyers", "OrderRequest", {"request_number__startswith": "REQ-"}),
        ("suppliers", "DeliveryNotice", {"description__in": DELIVERY_DESCRIPTIONS}),
        ("suppliers", "SupplyItem", {"name__in": [
            "Layer Mash", "Grower Pellets", "Multivitamins",
            "Newcastle Vaccine", "Egg Trays (bundle)",
        ]}),
        ("medicine", "MedicineRecord", {}),
        ("feeding", "FeedingRecord", {}),
        ("expenses", "ExpenseRecord", {"description__in": EXPENSE_DESCRIPTIONS}),
        ("expenses", "ExpenseCategory", {"name__in": ["Feeds", "Medicine", "Labor", "Utilities", "Maintenance"]}),
        ("sales", "SalesRecord", {"product_name__in": PRODUCT_NAMES}),
        ("sales", "Product", {"name__in": PRODUCT_NAMES}),
        ("deaths", "DeathRecord", {}),
        ("eggs", "EggProduction", {}),
        ("inventory", "InventoryTransaction", {"reference": "Opening stock"}),
        ("inventory", "InventoryItem", {"name__in": ["Layer Mash", "Grower Pellets", "Multivitamins", "Newcastle Vaccine", "Eggs (tray)", "Manure (sack)"]}),
        ("inventory", "Unit", {"abbreviation__in": ["kg", "sack", "tray", "pc", "btl"]}),
        ("inventory", "InventoryCategory", {"name__in": ["Feeds", "Medicine", "Vaccine", "Packaging", "Farm Produce"]}),
        # Only remove contacts the seed itself created (never portal-linked ones).
        ("buyers", "Buyer", {"name__in": BUYER_NAMES, "user__isnull": True}),
        ("suppliers", "Supplier", {"name__in": SUPPLIER_NAMES, "user__isnull": True}),
        ("flocks", "FlockBatch", {"batch_number__in": BATCH_NUMBERS}),
    ]:
        apps.get_model(app_label, model_name).objects.filter(**filters).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_role"),
        ("dashboard", "0001_initial"),
        ("flocks", "0001_initial"),
        ("inventory", "0002_inventoryitem_sales_product_type"),
        ("eggs", "0001_initial"),
        ("deaths", "0001_initial"),
        ("sales", "0004_product_created_by"),
        ("expenses", "0003_expenserecord_updated_at"),
        ("buyers", "0004_orderrequest_source"),
        ("suppliers", "0008_alter_deliverynotice_options"),
        ("feeding", "0001_initial"),
        ("medicine", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_farm_data, unseed_farm_data),
    ]