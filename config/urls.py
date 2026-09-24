from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path


def root_redirect(request):
    if request.user.is_authenticated:
        if request.user.is_external():
            return redirect("/portal/")
        return redirect("dashboard:index")
    return render(request, "landing/index.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("portal/", include("portal.urls")),
    path("", root_redirect, name="root"),
    path("", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("flocks/", include("flocks.urls")),
    path("inventory/", include("inventory.urls")),
    path("feeding/", include("feeding.urls")),
    path("medicine/", include("medicine.urls")),
    path("eggs/", include("eggs.urls")),
    path("mortality/", include("mortality.urls")),
    path("sales/", include("sales.urls")),
    path("expenses/", include("expenses.urls")),
    path("suppliers/", include("suppliers.urls")),
    path("buyers/", include("buyers.urls")),
    path("reports/", include("reports.urls")),
    path("notifications/", include("notifications.urls")),
    path("settings/", include("settings_app.urls")),
]
