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
