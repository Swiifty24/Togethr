import json
import math
import threading
import time
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views import defaults
from django.views.decorators.http import require_GET


# Nearby-city lookup: one reverse request per click, proxied through Django.
_CITY_CACHE_SECONDS = 300
_MIN_UPSTREAM_INTERVAL = 1.0  # Nominatim usage policy: max 1 request per second.
_UPSTREAM_TIMEOUT = 3
_CITY_ADDRESS_KEYS = ("city", "town", "village", "municipality", "county", "state_district")
_upstream_lock = threading.Lock()
_last_upstream_call = 0.0


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


# ---- Nearby cities ---------------------------------------------------------
def _coordinate(raw, low, high):
    """Return a finite float in range, or None for missing/invalid input."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not low <= value <= high:
        return None
    return value


def _clean_label(value):
    """Keep short, printable city labels; all form fields accept at most 100 chars."""
    if not isinstance(value, str):
        return ""
    label = " ".join(value.replace("\u00a0", " ").split())
    label = "".join(character for character in label if character.isprintable())
    return label[:100]


def _city_labels(payload):
    """Pick city/area names from Nominatim's address breakdown, never the full address."""
    address = payload.get("address") if isinstance(payload, dict) else None
    if not isinstance(address, dict):
        return []
    labels, seen = [], set()
    for key in _CITY_ADDRESS_KEYS:
        label = _clean_label(address.get(key))
        folded = label.casefold()
        if label and folded not in seen:
            seen.add(folded)
            labels.append(label)
    return labels[:3]


def _fetch_reverse(lat, lon):
    """Call the configured reverse-geocoding service politely, with a timeout."""
    global _last_upstream_call

    base, _, existing = settings.GEO_REVERSE_URL.partition("?")
    params = parse_qsl(existing, keep_blank_values=True) + [
        ("format", "jsonv2"),
        ("lat", f"{lat:.6f}"),
        ("lon", f"{lon:.6f}"),
        ("zoom", "10"),          # city-level detail, not a street address
        ("layer", "address"),
        ("addressdetails", "1"),
        ("accept-language", "en"),
    ]
    request = Request(
        f"{base}?{urlencode(params)}",
        headers={"User-Agent": settings.GEO_USER_AGENT, "Accept": "application/json"},
    )

    with _upstream_lock:
        wait = _MIN_UPSTREAM_INTERVAL - (time.monotonic() - _last_upstream_call)
        if wait > 0:
            time.sleep(wait)
        try:
            with urlopen(request, timeout=_UPSTREAM_TIMEOUT) as response:
                return json.load(response)
        finally:
            _last_upstream_call = time.monotonic()


@login_required
@require_GET
def city_suggestions(request):
    """GET /geo/cities/?lat=...&lon=... -> {"cities": ["City", "Area"]}."""
    lat = _coordinate(request.GET.get("lat"), -90, 90)
    lon = _coordinate(request.GET.get("lon"), -180, 180)
    if lat is None or lon is None:
        return JsonResponse({"error": "Valid lat and lon are required.", "cities": []}, status=400)

    # Rounded key groups nearby clicks together and avoids repeated upstream calls.
    cache_key = "geo:cities:{:.2f}:{:.2f}".format(lat, lon)
    cities = cache.get(cache_key)
    if cities is None:
        try:
            cities = _city_labels(_fetch_reverse(lat, lon))
        except (URLError, OSError, ValueError):
            return JsonResponse(
                {"error": "City lookup is unavailable right now.", "cities": []}, status=502
            )
        cache.set(cache_key, cities, _CITY_CACHE_SECONDS)

    return JsonResponse({"cities": cities})
