from django.shortcuts import redirect


class ExternalPortalAccessMiddleware:
    """External users (buyer/supplier roles) may only reach the portal and logout.

    Defense in depth: the portal views are already guarded by decorators, but this
    keeps stray @login_required-only internal views from leaking farm data.
    """

    ALLOWED_PREFIXES = ("/portal/", "/static/", "/media/", "/logout/", "/notifications/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = request.path
        if (
            user is not None
            and user.is_authenticated
            and user.is_external()
            and not path.startswith(self.ALLOWED_PREFIXES)
        ):
            return redirect("/portal/")
        return self.get_response(request)
