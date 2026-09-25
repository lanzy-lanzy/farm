from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from .views import (
    BuyerViewSet,
    EggProductionViewSet,
    ExpenseViewSet,
    FeedingViewSet,
    FlockViewSet,
    InventoryItemViewSet,
    LowStockInventoryView,
    MedicineViewSet,
    DeathViewSet,
    NotificationUnreadCountView,
    NotificationViewSet,
    SalesViewSet,
    SummaryView,
    SupplierViewSet,
    TrendsView,
)

router = DefaultRouter()
router.register("flocks", FlockViewSet, basename="flocks")
router.register("inventory", InventoryItemViewSet, basename="inventory")
router.register("eggs", EggProductionViewSet, basename="eggs")
router.register("deaths", DeathViewSet, basename="deaths")
router.register("feeding", FeedingViewSet, basename="feeding")
router.register("medicine", MedicineViewSet, basename="medicine")
router.register("sales", SalesViewSet, basename="sales")
router.register("expenses", ExpenseViewSet, basename="expenses")
router.register("suppliers", SupplierViewSet, basename="suppliers")
router.register("buyers", BuyerViewSet, basename="buyers")
router.register("notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="api-token"),
    # /api/v2/ is the write-capable portal + internal surface; everything above stays
    # read-only for the owner monitoring app and must not be mixed with v2 policies.
    path("v2/", include("api.urls_v2")),
    path("summary/", SummaryView.as_view(), name="api-summary"),
    path("trends/", TrendsView.as_view(), name="api-trends"),
    # Explicit routes must precede the router so they are not captured by an <pk> detail match.
    path("inventory/low-stock/", LowStockInventoryView.as_view(), name="api-inventory-low-stock"),
    path("notifications/unread-count/", NotificationUnreadCountView.as_view(), name="api-notifications-unread"),
    path("", include(router.urls)),
]
