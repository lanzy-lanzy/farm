import os

from django.conf import settings


def sidebar_context(request):
    return {"request": request}


def static_version(request):
    """Cache-busting token for compiled static assets.

    Derived from the modification time of the Tailwind-built stylesheet, so
    whenever ``npm run build`` regenerates it the ``?v=`` token changes and
    browsers fetch the fresh file automatically — no Ctrl+F5 required.
    """
    path = os.path.join(str(settings.BASE_DIR), "static", "css", "styles.css")
    try:
        version = str(int(os.path.getmtime(path)))
    except OSError:
        version = "0"
    return {"static_version": version}
