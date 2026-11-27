from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from .access import admin_or_owner_required, admin_required
from .forms import (
    AdminUserUpdateForm,
    LoginForm,
    PartnerRegistrationForm,
    UserRegistrationForm,
    UserUpdateForm,
)
from .models import User


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


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
    from buyers.models import Buyer
    from suppliers.models import Supplier

    tab = request.GET.get("tab", "all").strip().lower()
    if tab not in ("all", "staff", "buyers", "suppliers"):
        tab = "all"
    status_filter = request.GET.get("status", "all").strip().lower()
    if status_filter not in ("all", "active", "inactive", "pending"):
        status_filter = "all"
    q = request.GET.get("q", "").strip()

    base_qs = User.objects.select_related("buyer", "supplier").order_by("-date_joined")

    counts = {
        "all": base_qs.count(),
        "staff": base_qs.filter(role__in=User.INTERNAL_ROLES).count(),
        "buyers": base_qs.filter(role="buyer").count(),
        "suppliers": base_qs.filter(role="supplier").count(),
        "pending": (
            Buyer.objects.filter(verification_status="pending").count()
            + Supplier.objects.filter(verification_status="pending").count()
        ),
    }

    users = base_qs
    if tab == "staff":
        users = users.filter(role__in=User.INTERNAL_ROLES)
    elif tab == "buyers":
        users = users.filter(role="buyer")
    elif tab == "suppliers":
        users = users.filter(role="supplier")

    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "inactive":
        users = users.filter(is_active=False)
    elif status_filter == "pending":
        users = users.filter(
            Q(buyer__verification_status="pending")
            | Q(supplier__verification_status="pending")
        )

    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(buyer__name__icontains=q)
            | Q(supplier__name__icontains=q)
        ).distinct()

    user_rows = []
    for u in users:
        partner_profile = None
        if u.role == "buyer":
            partner_profile = getattr(u, "buyer", None)
        elif u.role == "supplier":
            partner_profile = getattr(u, "supplier", None)
        user_rows.append({"user": u, "partner": partner_profile})

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": users,
            "user_rows": user_rows,
            "tab": tab,
            "status_filter": status_filter,
            "q": q,
            "counts": counts,
        },
    )


@admin_or_owner_required
def user_detail(request, pk):
    target_user = get_object_or_404(
        User.objects.select_related("buyer", "supplier"), pk=pk
    )
    buyer_profile = getattr(target_user, "buyer", None) if target_user.role == "buyer" else None
    supplier_profile = getattr(target_user, "supplier", None) if target_user.role == "supplier" else None

    order_count = buyer_profile.order_requests.count() if buyer_profile else 0
    delivery_count = supplier_profile.delivery_notices.count() if supplier_profile else 0

    context = {
        "target_user": target_user,
        "buyer_profile": buyer_profile,
        "supplier_profile": supplier_profile,
        "order_count": order_count,
        "delivery_count": delivery_count,
    }
    template = "accounts/_detail.html" if is_htmx(request) else "accounts/user_detail.html"
    return render(request, template, context)


@admin_required
def user_create(request):
    from notifications.utils import log_activity

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            log_activity(
                request.user,
                "create",
                "User",
                new_user.pk,
                new_user.username,
                f"Created user ({new_user.get_role_display()})",
            )
            messages.success(request, f"User '{new_user.username}' created successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>var m=document.getElementById("modal-overlay");if(m)m.remove();window.location.reload()</script>'
                )
            return redirect("accounts:user_list")
    else:
        form = UserRegistrationForm()
    template = "accounts/_form.html" if is_htmx(request) else "accounts/user_form.html"
    return render(request, template, {"form": form})


@admin_required
def user_update(request, pk):
    from notifications.utils import log_activity

    target_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = AdminUserUpdateForm(request.POST, request.FILES, instance=target_user)
        if form.is_valid():
            updated = form.save()
            log_activity(
                request.user,
                "update",
                "User",
                updated.pk,
                updated.username,
                f"Updated user ({updated.get_role_display()})",
            )
            messages.success(request, f"User '{updated.username}' updated successfully.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>var m=document.getElementById("modal-overlay");if(m)m.remove();window.location.reload()</script>'
                )
            return redirect("accounts:user_list")
    else:
        form = AdminUserUpdateForm(instance=target_user)
    template = "accounts/_form.html" if is_htmx(request) else "accounts/user_form.html"
    return render(request, template, {"form": form, "target_user": target_user})


@admin_required
def user_delete(request, pk):
    from notifications.utils import log_activity

    target_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if target_user.pk == request.user.pk:
            messages.error(request, "You cannot delete your own account.")
            if is_htmx(request):
                return HttpResponse(
                    '<script>var m=document.getElementById("modal-overlay");if(m)m.remove();window.location.reload()</script>'
                )
            return redirect("accounts:user_list")
        username = target_user.username
        log_activity(request.user, "delete", "User", target_user.pk, username, "Deleted user")
        target_user.delete()
        messages.success(request, f"User '{username}' deleted successfully.")
        if is_htmx(request):
            return HttpResponse(
                '<script>var m=document.getElementById("modal-overlay");if(m)m.remove();window.location.reload()</script>'
            )
        return redirect("accounts:user_list")
    template = "accounts/_delete.html" if is_htmx(request) else "accounts/user_confirm_delete.html"
    return render(request, template, {"target_user": target_user})


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
