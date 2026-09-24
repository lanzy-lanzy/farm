from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_v2 import (
    ChangePasswordView,
    DeliveryNoticePortalViewSet,
    InternalDeliveryNoticeViewSet,
    InternalOrderRequestViewSet,
    OrderRequestPortalViewSet,
    PendingVerificationsView,
    PortalNotificationListView,
    PortalNotificationReadView,
    PortalProfileView,
    PurchaseHistoryView,
    SalesHistoryView,
    SupplyItemViewSet,
    SupplyUnitsView,
    VerificationActionView,
)

router = DefaultRouter()
router.register("portal/order-requests", OrderRequestPortalViewSet, basename="portal-order-requests")
router.register("portal/supply-items", SupplyItemViewSet, basename="portal-supply-items")
router.register("portal/delivery-notices", DeliveryNoticePortalViewSet, basename="portal-delivery-notices")
router.register("internal/order-requests", InternalOrderRequestViewSet, basename="internal-order-requests")
router.register("internal/delivery-notices", InternalDeliveryNoticeViewSet, basename="internal-delivery-notices")

urlpatterns = [
    path("auth/change-password/", ChangePasswordView.as_view(), name="api-v2-change-password"),
    path("portal/notifications/", PortalNotificationListView.as_view(), name="api-v2-portal-notifications"),
    path(
        "portal/notifications/<int:pk>/read/",
        PortalNotificationReadView.as_view(),
        name="api-v2-portal-notification-read",
    ),
    path("portal/profile/", PortalProfileView.as_view(), name="api-v2-portal-profile"),
    path("portal/sales-history/", SalesHistoryView.as_view(), name="api-v2-portal-sales-history"),
    path("portal/purchase-history/", PurchaseHistoryView.as_view(), name="api-v2-portal-purchase-history"),
    path("portal/units/", SupplyUnitsView.as_view(), name="api-v2-portal-units"),
    path("internal/verifications/pending/", PendingVerificationsView.as_view(), name="api-v2-verifications-pending"),
    path(
        "internal/verifications/<str:kind>/<int:pk>/<str:action_name>/",
        VerificationActionView.as_view(),
        name="api-v2-verification-action",
    ),
    path("", include(router.urls)),
]
