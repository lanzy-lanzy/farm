"""Automated Buyer & Admin OrderRequest workflow with configurable business rules.

Rules are stored in ``settings_app.SystemSetting`` (falling back to Django settings)
so administrators can adjust automation behaviour without redeploying:

- ``order_auto_complete_on_delivered`` (default True): marking an order Delivered
  automatically transitions it to Completed (Product Received) and records the sale.
- ``order_auto_complete_on_buyer_accept`` (default True): when a buyer accepts an
  order/quote, the system automatically completes it and records the sale.
- ``order_auto_create_sale_on_complete`` (default True): completing an order creates
  its linked SalesRecord and deducts mapped inventory automatically.
"""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from inventory.services import deduct_for_sale, sale_stock_block_reason
from notifications.utils import log_activity, notify_team, notify_user
from sales.models import SalesRecord
from settings_app.models import SystemSetting

RULE_KEYS = (
    ("order_auto_complete_on_delivered", "ORDER_AUTO_COMPLETE_ON_DELIVERED", True),
    ("order_auto_complete_on_buyer_accept", "ORDER_AUTO_COMPLETE_ON_BUYER_ACCEPT", True),
    ("order_auto_create_sale_on_complete", "ORDER_AUTO_CREATE_SALE_ON_COMPLETE", True),
)


class WorkflowError(Exception):
    """Raised when an order status transition is invalid or blocked by stock/rules."""


def _parse_bool(raw, default=True):
    if isinstance(raw, bool):
        return raw
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def get_workflow_rules():
    """Return the active order-automation business rules."""
    rules = {}
    for setting_key, django_key, fallback in RULE_KEYS:
        default_val = getattr(settings, django_key, fallback)
        raw = SystemSetting.objects.filter(key=setting_key).values_list("value", flat=True).first()
        rules[setting_key] = _parse_bool(raw, default_val)
    return rules


def save_workflow_rules(*, auto_complete_on_delivered, auto_complete_on_buyer_accept, auto_create_sale_on_complete):
    """Persist order-automation business rules to SystemSetting."""
    SystemSetting.set_setting(
        "order_auto_complete_on_delivered",
        "true" if auto_complete_on_delivered else "false",
        "Automatically mark orders Completed (Product Received) when marked Delivered.",
    )
    SystemSetting.set_setting(
        "order_auto_complete_on_buyer_accept",
        "true" if auto_complete_on_buyer_accept else "false",
        "Automatically mark orders Completed (Product Received) when accepted by the buyer.",
    )
    SystemSetting.set_setting(
        "order_auto_create_sale_on_complete",
        "true" if auto_create_sale_on_complete else "false",
        "Automatically create the linked SalesRecord and deduct inventory on completion.",
    )


def complete_order(order, actor, *, note=None, notify_buyer_title=None, notify_team_msg=None):
    """Transition an order to Completed, auto-creating its SalesRecord & deducting stock."""
    rules = get_workflow_rules()
    auto_sale = rules["order_auto_create_sale_on_complete"]
    record = order.sales_record

    if auto_sale and record is None:
        stock_reason = sale_stock_block_reason(order.product_type, order.quantity)
        if stock_reason:
            raise WorkflowError(f"Insufficient stock — {stock_reason}")

    with transaction.atomic():
        if auto_sale and record is None:
            unit_price = order.effective_unit_price
            if unit_price is None:
                unit_price = Decimal("0.00")
            total = order.quantity * unit_price
            record = SalesRecord.objects.create(
                product_type=order.product_type,
                buyer=order.buyer,
                product_name=order.product_name,
                quantity=order.quantity,
                unit_price=unit_price,
                total_amount=total,
                date_sold=timezone.localdate(),
                payment_status="paid",
                amount_paid=total,
                recorded_by=actor,
                notes=f"Auto-completed from order {order.request_number}",
            )
            deduct_for_sale(record, user=actor)
            order.sales_record = record
            log_activity(
                actor,
                "create",
                "SalesRecord",
                record.pk,
                str(record),
                f"Auto-recorded sale on completion of {order.request_number}",
            )

        order.status = "completed"
        if note:
            order.staff_note = note
        order.save()

    log_activity(
        actor,
        "update",
        "OrderRequest",
        order.pk,
        order.request_number,
        "Order automatically marked Completed (Product Received)",
    )

    if order.buyer.user_id:
        notify_user(
            order.buyer.user,
            "order_request",
            notify_buyer_title or f"Order {order.request_number} completed",
            f"Your order for {order.quantity} {order.product_name} is now Completed (Product Received).",
            link=f"/portal/buyer/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
    if notify_team_msg:
        notify_team(
            "order_request",
            f"Order {order.request_number} completed",
            notify_team_msg,
            link=f"/sales/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
    return order, record


def advance_order(order, action, actor, *, note=None):
    """Execute one workflow transition and apply automation rules.

    Supported actions:
      - Admin: ``approve``, ``process``, ``out_for_delivery``, ``deliver``
      - Buyer: ``buyer_accept``, ``confirm_received``
    """
    rules = get_workflow_rules()

    if action == "approve":
        if not order.can_approve():
            raise WorkflowError("Only a Pending Approval order can be approved.")
        order.status = "approved"
        if order.quoted_unit_price is None and order.requested_unit_price is not None:
            order.quoted_unit_price = order.requested_unit_price
        if note:
            order.staff_note = note
        order.save()
        log_activity(actor, "update", "OrderRequest", order.pk, order.request_number, "Approved order")
        notify_user(
            order.buyer.user,
            "order_request",
            f"Order {order.request_number} approved",
            f"Your order for {order.quantity} {order.product_name} has been approved.",
            link=f"/portal/buyer/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        return order, f"Order {order.request_number} approved."

    if action == "process":
        if not order.can_start_processing():
            raise WorkflowError("Only an Approved order can move to Processing.")
        order.status = "processing"
        if note:
            order.staff_note = note
        order.save()
        log_activity(actor, "update", "OrderRequest", order.pk, order.request_number, "Moved to Processing")
        notify_user(
            order.buyer.user,
            "order_request",
            f"Order {order.request_number} is being processed",
            f"The farm is now preparing your order ({order.quantity} {order.product_name}).",
            link=f"/portal/buyer/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        return order, f"Order {order.request_number} is now Processing."

    if action == "out_for_delivery":
        if not order.can_mark_out_for_delivery():
            raise WorkflowError("Only a Processing order can be marked Out for Delivery.")
        order.status = "out_for_delivery"
        if note:
            order.staff_note = note
        order.save()
        log_activity(actor, "update", "OrderRequest", order.pk, order.request_number, "Marked Out for Delivery")
        notify_user(
            order.buyer.user,
            "order_request",
            f"Order {order.request_number} is out for delivery",
            f"Your order ({order.quantity} {order.product_name}) is on its way.",
            link=f"/portal/buyer/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        return order, f"Order {order.request_number} is Out for Delivery."

    if action == "deliver":
        if not order.can_mark_delivered():
            raise WorkflowError("This order cannot be marked Delivered in its current status.")
        if rules["order_auto_complete_on_delivered"]:
            order, _ = complete_order(
                order,
                actor,
                note=note,
                notify_buyer_title=f"Order {order.request_number} delivered & completed",
            )
            return order, f"Order {order.request_number} marked Delivered and automatically Completed."
        order.status = "delivered"
        if note:
            order.staff_note = note
        order.save()
        log_activity(actor, "update", "OrderRequest", order.pk, order.request_number, "Marked Delivered")
        notify_user(
            order.buyer.user,
            "order_request",
            f"Order {order.request_number} delivered",
            "Your order has been delivered. Confirm receipt in your portal to complete it.",
            link=f"/portal/buyer/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        return order, f"Order {order.request_number} marked as Delivered."

    if action == "confirm_received":
        if not order.can_confirm_received():
            raise WorkflowError("You can only accept this order once it is marked Out for Delivery by the admin.")
        auto_sale = rules["order_auto_create_sale_on_complete"]
        record = order.sales_record
        if auto_sale and record is None:
            stock_reason = sale_stock_block_reason(order.product_type, order.quantity)
            if stock_reason:
                raise WorkflowError(f"Insufficient stock — {stock_reason}")
        with transaction.atomic():
            if auto_sale and record is None:
                unit_price = order.effective_unit_price if order.effective_unit_price is not None else Decimal("0.00")
                total = order.quantity * unit_price
                record = SalesRecord.objects.create(
                    product_type=order.product_type,
                    buyer=order.buyer,
                    product_name=order.product_name,
                    quantity=order.quantity,
                    unit_price=unit_price,
                    total_amount=total,
                    date_sold=timezone.localdate(),
                    payment_status="paid",
                    amount_paid=total,
                    recorded_by=actor,
                    notes=f"Auto-recorded on buyer delivery acceptance for {order.request_number}",
                )
                deduct_for_sale(record, user=actor)
                order.sales_record = record
                log_activity(
                    actor,
                    "create",
                    "SalesRecord",
                    record.pk,
                    str(record),
                    f"Auto-recorded sale on delivery acceptance of {order.request_number}",
                )
            order.status = "delivered"
            order.save()
        log_activity(
            actor,
            "update",
            "OrderRequest",
            order.pk,
            order.request_number,
            "Buyer accepted order — automatically marked Delivered",
        )
        notify_team(
            "order_request",
            f"Order {order.request_number} delivered (accepted by buyer)",
            f"{order.buyer.name} accepted {order.request_number}. Order is now marked Delivered and ready for receipt printing.",
            link=f"/sales/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        return order, f"Order {order.request_number} accepted and marked Delivered."

    if action == "buyer_accept":
        if not order.can_accept():
            msg = (
                "This quote has expired; ask the farm to re-quote."
                if order.is_stale
                else "Only a quoted request can be accepted."
            )
            raise WorkflowError(msg)
        if rules["order_auto_complete_on_buyer_accept"]:
            order, _ = complete_order(
                order,
                actor,
                notify_team_msg=f"{order.buyer.name} accepted {order.request_number}. Automatically marked Completed.",
            )
            return order, f"Order {order.request_number} accepted and automatically Completed."
        order.status = "accepted"
        order.save()
        notify_team(
            "order_request",
            f"Quote accepted for {order.request_number}",
            f"{order.buyer.name} accepted the quote.",
            link=f"/sales/requests/{order.pk}/",
            target=f"order_request:{order.pk}",
        )
        return order, "Quote accepted. The farm will now process your order."

    raise WorkflowError(f"Unknown order workflow action: {action}")
