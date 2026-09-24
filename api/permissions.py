from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwner(BasePermission):
    """Allow only the farm owner (or a superuser, for convenience) and only safe/read methods.

    The monitoring API is intentionally read-only: any non-GET request is rejected here,
    so even if a write route were added later it could not mutate data through this permission.
    """

    message = "Farm owner access is required for this resource."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not (user.is_owner() or user.is_superuser):
            return False
        return request.method in SAFE_METHODS


class IsInternalUser(BasePermission):
    """Farm staff/admin/owner (or superuser). Used by /api/v2/ internal endpoints."""

    message = "Farm staff access is required for this resource."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (getattr(user, "is_internal", lambda: False)() or user.is_superuser)
        )


class IsAdminOrOwner(BasePermission):
    """Administrator or farm owner only — mirrors accounts.access.admin_or_owner_required.

    Used for verification (activate/reject) endpoints: staff may triage queues but
    must not be able to grant themselves or others portal access.
    """

    message = "Administrator or owner access is required for this resource."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_admin_user() or user.is_owner() or user.is_superuser)
        )


class IsVerifiedPortalUser(BasePermission):
    """External buyer/supplier with an approved, active profile.

    Set `required_role` on a subclass (or view) to pin the role.
    Object-level scoping to the user's own records happens in get_queryset(),
    never from client-supplied IDs.
    """

    message = "A verified buyer or supplier account is required for this resource."
    required_role = None

    def has_permission(self, request, view):
        user = request.user
        if not (
            user
            and user.is_authenticated
            and getattr(user, "is_external", lambda: False)()
        ):
            return False
        required = getattr(view, "required_role", self.required_role)
        if required and user.role != required:
            return False
        profile = getattr(user, user.role, None)
        return bool(
            profile
            and profile.verification_status == "approved"
            and profile.is_active
        )


class IsVerifiedBuyer(IsVerifiedPortalUser):
    required_role = "buyer"


class IsVerifiedSupplier(IsVerifiedPortalUser):
    required_role = "supplier"
