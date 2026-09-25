"""Single entry point for inventory quantity changes made outside the inventory UI.

Delivery receipts add stock, sales deduct it; both route through adjust_stock so the
transaction row, the quantity math and the low-stock alert stay in one place.
"""

from django.db import transaction

from notifications.utils import check_and_notify_inventory

from .models import InventoryItem, InventoryTransaction


def adjust_stock(item, transaction_type, quantity, reference, user=None, notes=None):
    with transaction.atomic():
        txn = InventoryTransaction.objects.create(
            item=item,
            transaction_type=transaction_type,
            quantity=quantity,
            reference=reference,
            notes=notes,
            created_by=user,
        )
    check_and_notify_inventory(txn.item)
    return txn


def mapped_item_for_product(product_type):
    """The InventoryItem whose stock sales of this product_type draw from, if any."""
    return InventoryItem.objects.filter(sales_product_type=product_type, is_active=True).first()


def sale_stock_block_reason(product_type, quantity):
    """A reason the sale would oversell, or None. No mapped item means stock is untracked."""
    item = mapped_item_for_product(product_type)
    if item is None:
        return None
    if item.quantity < quantity:
        return (
            f"Only {item.quantity} {item.unit.abbreviation} of {item.name} in stock — "
            f"cannot sell {quantity}. Receive the delivery or adjust stock first."
        )
    return None


def deduct_for_sale(sale, user=None):
    item = mapped_item_for_product(sale.product_type)
    if item is None:
        return None
    return adjust_stock(
        item,
        "out",
        sale.quantity,
        reference=f"Sales Record #{sale.pk}",
        user=user,
    )


def stock_target_for_notice(notice):
    """Explicit receive-time booking wins; then the catalog mapping; then no stock movement."""
    if notice.inventory_item_id:
        return notice.inventory_item
    if notice.supply_item_id:
        return notice.supply_item.inventory_item
    return None


def receive_for_notice(notice, user=None):
    item = stock_target_for_notice(notice)
    if item is None:
        return None
    return adjust_stock(
        item,
        "in",
        notice.quantity,
        reference=f"Delivery Notice #{notice.pk}",
        user=user,
    )
