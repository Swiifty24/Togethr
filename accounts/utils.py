from django.conf import settings
from django.urls import reverse


def home_url_for(user):
    """Where a signed-in user lands, according to their role."""
    return reverse("adminpanel:home") if user.is_superuser else reverse("activities:home")


def get_client_ip(request):
    """
    REMOTE_ADDR by default. X-Forwarded-For is only honoured when
    TRUST_PROXY_HEADERS=True, because otherwise clients could spoof it to dodge
    the login rate limit.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def mask_email(email):
    local, _, domain = email.partition("@")
    if not domain:
        return email
    return f"{local[:1]}{'*' * max(len(local) - 1, 2)}@{domain}"
