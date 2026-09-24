import os

from django.conf import settings


def sidebar_context(request):
    return {"request": request}


def static_version(request):
    """Cache-busting token for compiled static assets.

    Derived from the modification time of the Tailwind-built stylesheet, so
    whenever ``npm run build`` regenerates it the ``?v=`` token changes and
    browsers fetch the fresh file automatically — no Ctrl+F5 required.
    """
    path = os.path.join(str(settings.BASE_DIR), "static", "css", "styles.css")
    try:
        version = str(int(os.path.getmtime(path)))
    except OSError:
        version = "0"
    return {"static_version": version}


def queue_context(request):
    ctx = {"open_order_requests": 0, "open_delivery_notices": 0, "pending_verifications": 0}
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or user.is_external():
        return ctx
    from buyers.models import Buyer, OrderRequest
    from suppliers.models import DeliveryNotice, Supplier

    ctx["open_order_requests"] = OrderRequest.objects.filter(
        status__in=["submitted", "under_review", "quoted", "accepted"]
    ).count()
    ctx["open_delivery_notices"] = DeliveryNotice.objects.filter(status="announced").count()
    ctx["pending_verifications"] = (
        Buyer.objects.filter(verification_status="pending").count()
        + Supplier.objects.filter(verification_status="pending").count()
    )
    return ctx
