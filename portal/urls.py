from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import redirect
from django.urls import path, reverse_lazy

from buyers import portal_views as buyer_views
from suppliers import portal_views as supplier_views

from .forms import PortalPasswordChangeForm

app_name = "portal"


def portal_home(request):
    if request.user.role == "buyer":
        return redirect("portal:buyer_home")
    if request.user.role == "supplier":
        return redirect("portal:supplier_home")
    return redirect("dashboard:index")


password_change_view = PasswordChangeView.as_view(
    template_name="portal/password_change.html",
    success_url=reverse_lazy("portal:home"),
    form_class=PortalPasswordChangeForm,
)

urlpatterns = [
    path("", login_required(portal_home), name="home"),
    path("password/", login_required(password_change_view), name="password_change"),
    # Buyer portal
    path("buyer/", buyer_views.buyer_home, name="buyer_home"),
    path("buyer/requests/", buyer_views.order_request_list, name="buyer_requests"),
    path("buyer/requests/new/", buyer_views.order_request_create, name="buyer_request_create"),
    path("buyer/requests/<int:pk>/", buyer_views.order_request_detail, name="buyer_request_detail"),
    path("buyer/requests/<int:pk>/respond/", buyer_views.order_request_respond, name="buyer_request_respond"),
    path("buyer/requests/<int:pk>/cancel/", buyer_views.order_request_cancel, name="buyer_request_cancel"),
    path("buyer/profile/", buyer_views.buyer_profile, name="buyer_profile"),
    # Supplier portal
    path("supplier/", supplier_views.supplier_home, name="supplier_home"),
    path("supplier/catalog/", supplier_views.catalog_list, name="supplier_catalog"),
    path("supplier/catalog/create/", supplier_views.catalog_create, name="supplier_catalog_create"),
    path("supplier/catalog/<int:pk>/edit/", supplier_views.catalog_update, name="supplier_catalog_update"),
    path("supplier/catalog/<int:pk>/delete/", supplier_views.catalog_delete, name="supplier_catalog_delete"),
    path("supplier/deliveries/", supplier_views.delivery_notice_list, name="supplier_deliveries"),
    path("supplier/deliveries/create/", supplier_views.delivery_notice_create, name="supplier_delivery_create"),
    path("supplier/deliveries/<int:pk>/cancel/", supplier_views.delivery_notice_cancel, name="supplier_delivery_cancel"),
    path("supplier/deliveries/<int:pk>/respond/", supplier_views.delivery_notice_respond, name="supplier_delivery_respond"),
    path("supplier/history/", supplier_views.purchase_history, name="supplier_history"),
    path("supplier/profile/", supplier_views.supplier_profile, name="supplier_profile"),
]
