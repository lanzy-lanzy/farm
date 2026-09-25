"""Shared helpers for the HTMX modal convention used across the app.

A modal partial POSTs to its view; on success the view replies with this script so
the dialog drops itself and the fresh page (with its flash message) comes in.
Guarded because the same reply is also returned for HTMX posts made outside a dialog.
"""

from django.http import HttpResponse

MODAL_CLOSE_SCRIPT = (
    '<script>var m=document.getElementById("modal-overlay");'
    "if(m)m.remove();window.location.reload()</script>"
)


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def modal_closed():
    """HTMX reply that closes an open modal and reloads the page underneath it."""
    return HttpResponse(MODAL_CLOSE_SCRIPT)
