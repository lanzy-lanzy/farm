from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from .access import admin_or_owner_required, admin_required
from .forms import LoginForm, PartnerRegistrationForm, UserRegistrationForm, UserUpdateForm
from .models import User


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"

    def get_success_url(self):
        if self.request.user.is_authenticated and self.request.user.is_external():
            return reverse("portal:home")
        return super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        return response


def register(request, default_role=None):
    """Public self-registration for Buyer and Supplier accounts (requires admin approval)."""
    from notifications.utils import log_activity, notify_admins_and_owners

    if request.user.is_authenticated:
        if request.user.is_external():
            return redirect("portal:home")
        return redirect("dashboard:index")

    requested_role = default_role or request.GET.get("role", "buyer")
    if requested_role not in ("buyer", "supplier"):
        requested_role = "buyer"

    if request.method == "POST":
        form = PartnerRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user, profile = form.save()
                role = user.role
                role_label = "Buyer" if role == "buyer" else "Supplier"
                notify_admins_and_owners(
                    "account",
                    f"New {role_label} registration: {profile.name}",
                    f"{profile.name} (@{user.username}) registered as a {role_label.lower()} "
                    "and is awaiting verification.",
                    link=reverse("accounts:verification_queue"),
                    target=f"verification:{role}:{profile.pk}",
                )
                log_activity(
                    user,
                    "create",
                    role_label,
                    profile.pk,
                    profile.name,
                    f"Self-registered as {role_label.lower()} (pending approval)",
                )
            messages.success(
                request,
                f"Registration submitted for {profile.name} (@{user.username}). "
                "Your account is pending administrator approval — you will be able to sign in once approved.",
            )
            return redirect("accounts:login")
    else:
        form = PartnerRegistrationForm(initial={"role": requested_role})

    selected_role = form["role"].value() or requested_role
    if selected_role not in ("buyer", "supplier"):
        selected_role = "buyer"

    return render(
        request,
        "accounts/register.html",
        {"form": form, "selected_role": selected_role},
    )


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


@admin_or_owner_required
def user_list(request):
    users = User.objects.all().order_by("-date_joined")
    return render(request, "accounts/user_list.html", {"users": users})


@admin_required
def user_create(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:user_list")
    else:
        form = UserRegistrationForm()
    return render(request, "accounts/user_form.html", {"form": form})


@admin_required
def user_update(request, pk):
    user = User.objects.get(pk=pk)
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect("accounts:user_list")
    else:
        form = UserUpdateForm(instance=user)
    return render(request, "accounts/user_form.html", {"form": form, "user": user})


@admin_required
def user_delete(request, pk):
    user = User.objects.get(pk=pk)
    if request.method == "POST":
        user.delete()
        return redirect("accounts:user_list")
    return render(request, "accounts/user_confirm_delete.html", {"user": user})


@admin_or_owner_required
def reset_portal_password(request, pk):
    """Issue a fresh temporary password for an external (buyer/supplier) portal user."""
    from django.utils.crypto import get_random_string

    from notifications.utils import log_activity

    target = get_object_or_404(User, pk=pk)
    if request.method != "POST":
        return redirect("accounts:user_list")
    if target.role not in User.EXTERNAL_ROLES:
        messages.error(request, "Only external portal accounts can be reset here.")
        return redirect("accounts:user_list")
    password = get_random_string(10)
    target.set_password(password)
    target.is_active = True
    target.save()
    messages.success(
        request,
        f"New temporary password for {target.username}: {password}. "
        "Share it with the user; they should change it from their portal.",
    )
    log_activity(request.user, "update", "User", target.pk, target.username, "Reset portal password")
    return redirect("accounts:user_list")


@login_required
def profile(request):
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("accounts:profile")
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@admin_or_owner_required
def verification_queue(request):
    from buyers.models import Buyer
    from suppliers.models import Supplier

    pending_buyers = Buyer.objects.exclude(verification_status="approved").order_by("-created_at")
    pending_suppliers = Supplier.objects.exclude(verification_status="approved").order_by("-created_at")
    return render(
        request,
        "accounts/verify_queue.html",
        {"pending_buyers": pending_buyers, "pending_suppliers": pending_suppliers},
    )


@admin_or_owner_required
def verification_action(request, kind, pk):
    from buyers.models import Buyer
    from suppliers.models import Supplier
    from notifications.utils import log_activity, notify_user

    if request.method != "POST":
        return redirect("accounts:verification_queue")

    if kind not in ("buyer", "supplier"):
        messages.error(request, "Unknown account type.")
        return redirect("accounts:verification_queue")

    model = Buyer if kind == "buyer" else Supplier
    profile_obj = get_object_or_404(model, pk=pk)
    action = request.POST.get("action")

    if action == "approve":
        profile_obj.verification_status = "approved"
        profile_obj.rejection_reason = None
        profile_obj.verified_by = request.user
        profile_obj.verified_at = timezone.now()
        if profile_obj.user:
            profile_obj.user.is_active = profile_obj.is_active
            profile_obj.user.save(update_fields=["is_active"])
            notify_user(
                profile_obj.user,
                "account",
                "Account approved",
                f"Your {kind} account ({profile_obj.name}) has been approved. Welcome to the portal!",
                link="/portal/",
            )
        messages.success(request, f"{profile_obj.name} approved.")
    elif action == "reject":
        profile_obj.verification_status = "rejected"
        profile_obj.rejection_reason = request.POST.get("reason", "").strip() or None
        profile_obj.verified_by = request.user
        profile_obj.verified_at = timezone.now()
        if profile_obj.user:
            profile_obj.user.is_active = False
            profile_obj.user.save(update_fields=["is_active"])
        messages.success(request, f"{profile_obj.name} rejected.")
    else:
        messages.error(request, "Unknown action.")
        return redirect("accounts:verification_queue")

    profile_obj.save()
    log_activity(
        request.user, "update", model.__name__, profile_obj.pk,
        profile_obj.name, f"Verification {action}",
    )
    return redirect("accounts:verification_queue")
