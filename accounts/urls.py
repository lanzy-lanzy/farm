from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_update, name="user_update"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:pk>/reset-portal-password/", views.reset_portal_password, name="reset_portal_password"),
    path("verify/queue/", views.verification_queue, name="verification_queue"),
    path("verify/<str:kind>/<int:pk>/", views.verification_action, name="verification_action"),
]
