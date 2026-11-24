from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views import defaults


def landing(request):
    return render(request, "core/landing.html")


def error_preview(request, code):
    """DEBUG-only: lets you look at the custom error pages (/_errors/404/ etc.)."""
    if not settings.DEBUG:
        raise Http404
    handlers = {
        400: lambda: defaults.bad_request(request, Exception()),
        403: lambda: defaults.permission_denied(request, Exception()),
        404: lambda: defaults.page_not_found(request, Exception()),
        500: lambda: defaults.server_error(request),
    }
    if code not in handlers:
        raise Http404
    return handlers[code]()
