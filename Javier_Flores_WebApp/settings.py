"""
Django settings for Togethr.

All secrets and environment-specific values come from environment variables
(loaded from a local ".env" file). See ".env.example".

This project keeps its original settings package name, Javier_Flores_WebApp.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------------------------------
# Environment helpers
# --------------------------------------------------------------------------
def env(name, default=None):
    value = os.environ.get(name)
    return default if value in (None, "") else value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(env(name, default))
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f"Environment variable {name} must be an integer.")


def env_list(name, default=""):
    return [item.strip() for item in str(env(name, default)).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is not set. Copy .env.example to .env and set a "
        "long random value (see the comment at the top of .env.example)."
    )
if not DEBUG and SECRET_KEY.startswith("change-me"):
    raise ImproperlyConfigured("Set a real DJANGO_SECRET_KEY before running with DEBUG off.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

SITE_NAME = env("SITE_NAME", "Togethr")

DJANGO_ADMIN_URL = env("DJANGO_ADMIN_URL", "django-admin/").lstrip("/")
if not DJANGO_ADMIN_URL.endswith("/"):
    DJANGO_ADMIN_URL += "/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Togethr apps
    "core",
    "accounts",
    "members",
    "activities",
    "adminpanel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "Javier_Flores_WebApp.urls"
WSGI_APPLICATION = "Javier_Flores_WebApp.wsgi.application"
ASGI_APPLICATION = "Javier_Flores_WebApp.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]


# --------------------------------------------------------------------------
# Database: MySQL / MariaDB, database name "togethr"
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", "togethr"),
        "USER": env("DB_USER", "root"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Authentication & passwords
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "activities:home"
LOGOUT_REDIRECT_URL = "core:landing"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("username", "email", "full_name")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "accounts.validators.PasswordComplexityValidator"},
]

# Django's default hasher is PBKDF2-SHA256; passwords are never stored in plain text.
PASSWORD_RESET_TIMEOUT = 60 * 60  # reset links are valid for one hour

# Sessions & CSRF
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # "Remember me" lasts 14 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", False)

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    if TRUST_PROXY_HEADERS:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --------------------------------------------------------------------------
# Account security tuning
# --------------------------------------------------------------------------
VERIFICATION_CODE_TTL_MINUTES = env_int("VERIFICATION_CODE_TTL_MINUTES", 10)
VERIFICATION_MAX_ATTEMPTS = env_int("VERIFICATION_MAX_ATTEMPTS", 5)
VERIFICATION_RESEND_COOLDOWN_SECONDS = env_int("VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)
VERIFICATION_MAX_SENDS_PER_HOUR = env_int("VERIFICATION_MAX_SENDS_PER_HOUR", 5)

LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_MAX_ATTEMPTS_PER_IP = env_int("LOGIN_MAX_ATTEMPTS_PER_IP", 20)
LOGIN_LOCKOUT_MINUTES = env_int("LOGIN_LOCKOUT_MINUTES", 15)
PASSWORD_RESET_MAX_REQUESTS_PER_HOUR = env_int("PASSWORD_RESET_MAX_REQUESTS_PER_HOUR", 5)


# --------------------------------------------------------------------------
# Email (Gmail SMTP by default; credentials come from the environment)
# --------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    f"{SITE_NAME} <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else f"{SITE_NAME} <noreply@togethr.local>",
)


# --------------------------------------------------------------------------
# i18n, static files
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Manila")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# User uploads (activity covers, profile pictures)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024

MESSAGE_TAGS = {40: "error"}  # Django already maps ERROR -> "error"; kept explicit for templates.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "accounts": {"handlers": ["console"], "level": "INFO"},
        "django.security": {"handlers": ["console"], "level": "WARNING"},
    },
}
