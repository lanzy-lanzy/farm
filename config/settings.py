"""
Django settings for config project.
Poultry Farm Record and Inventory Management System
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Production values come from environment variables (Seenode dashboard).
# Defaults keep local development working unchanged.
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-#%qpiae_!(5v00-%c_+5upfb#h!w@$++evp@_t=ay35&1_^)i4",
)

DEBUG = os.environ.get("DEBUG", "true").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

# Needed for HTTPS form posts on the deployed domain, e.g.
# CSRF_TRUSTED_ORIGINS=https://your-app.seenode.app
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Persistent data directory. On Seenode, mount a storage volume at /data and
# set DATA_DIR=/data so the SQLite database and uploaded media survive
# redeploys. Locally it defaults to the project root (unchanged behavior).
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_tailwind",
    "rest_framework",
    "rest_framework.authtoken",
    "api",
    "accounts",
    "dashboard",
    "flocks",
    "inventory",
    "feeding",
    "medicine",
    "eggs",
    "deaths",
    "sales",
    "expenses",
    "suppliers",
    "buyers",
    "reports",
    "notifications",
    "settings_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.ExternalPortalAccessMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notification_context",
                "config.context_processors.sidebar_context",
                "config.context_processors.static_version",
                "config.context_processors.queue_context",
                "config.context_processors.portal_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise serves collected static files in production (no nginx needed).
# CompressedStaticFilesStorage (no manifest) avoids hard failures on any
# template-referenced file that is missing from the static dirs.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "accounts:login"

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ---- Django REST Framework (read-only monitoring API for the mobile app) ----
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# ---- Buyer/supplier workflow ----
# Days before an unanswered quote is considered stale and must be re-quoted.
ORDER_REQUEST_QUOTE_STALE_DAYS = 7

# ---- Production hardening (active when DEBUG=false) ----
if not DEBUG:
    # Seenode terminates TLS at its proxy and forwards this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
