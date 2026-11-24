from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache

from .utils import home_url_for


def anonymous_required(view):
    """Signed-in users have no business on the login/register pages."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(home_url_for(request.user))
        return view(request, *args, **kwargs)

    return wrapper


def superuser_required(view):
    """
    Server-side guard for every administrator view. Anonymous visitors are sent
    to the login page; signed-in regular users get a 403.
    """

    @wraps(view)
    @never_cache
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_active and request.user.is_superuser):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
