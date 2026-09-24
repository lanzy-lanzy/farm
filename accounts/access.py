from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from .models import User


def external_portal_required(role):
    """Guard portal views: user must have the given external role and an approved profile."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            profile = getattr(user, role, None)
            if (
                user.role != role
                or profile is None
                or profile.verification_status != "approved"
                or not profile.is_active
            ):
                return HttpResponseForbidden(
                    "Your account does not have access to this portal."
                )
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def internal_only(view):
    """Guard farm-internal views: admin/owner/staff roles only (belt and braces with middleware)."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_internal():
            return HttpResponseForbidden("Internal access required.")
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin_user():
            return HttpResponseForbidden("Administrator access required.")
        return view(request, *args, **kwargs)

    return wrapper


def admin_or_owner_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_admin_user() or request.user.is_owner()):
            return HttpResponseForbidden("Administrator or owner access required.")
        return view(request, *args, **kwargs)

    return wrapper


def staff_or_admin_required(view):
    """Guard developer/infrastructure views: Django staff flag or the admin role."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.role == "admin"):
            return HttpResponseForbidden("Administrator access required.")
        return view(request, *args, **kwargs)

    return wrapper


def create_portal_account(profile_obj, role, operator):
    """Staff-vouched account creation: link a new User to a Buyer/Supplier, pre-approved."""
    if profile_obj.user_id:
        raise ValueError(f"{profile_obj.name} already has a linked portal account.")
    base = slugify(profile_obj.name)[:24] or role
    username = base
    suffix = 2
    while User.objects.filter(username=username).exists():
        username = f"{base}{suffix}"
        suffix += 1
    password = get_random_string(10)
    user = User.objects.create_user(
        username=username,
        email=profile_obj.email or "",
        password=password,
        role=role,
        first_name=profile_obj.name[:30],
    )
    profile_obj.user = user
    profile_obj.verification_status = "approved"
    profile_obj.rejection_reason = None
    profile_obj.verified_by = operator
    profile_obj.verified_at = timezone.now()
    profile_obj.save()
    return user, password
