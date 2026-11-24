from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.models import ActivityLog, Notification
from accounts.services import log_activity, notify

from .forms import ChangePasswordForm, ProfileForm


@login_required
@never_cache
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(ActivityLog.PROFILE_UPDATED, user=request.user, request=request, description="Profile updated")
        messages.success(request, "Your profile has been updated.")
        return redirect("members:profile")
    return render(request, "members/profile.html", {"form": form})


@login_required
@never_cache
def settings_view(request):
    form = ChangePasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # keep this session signed in
        log_activity(ActivityLog.PASSWORD_CHANGED, user=user, request=request, description="Password changed")
        notify(user, "Password changed", "Your password was updated successfully.", Notification.SUCCESS)
        messages.success(request, "Your password has been changed.")
        return redirect("members:settings")
    security_activity = request.user.activities.filter(action__in=ActivityLog.SECURITY_ACTIONS)[:8]
    return render(request, "members/settings.html", {"form": form, "security_activity": security_activity})


@login_required
@never_cache
def notifications(request):
    page = Paginator(request.user.notifications.all(), 20).get_page(request.GET.get("page"))
    return render(request, "members/notifications.html", {"page": page})


@login_required
@never_cache
@require_POST
def notification_open(request, pk):
    """Mark one notification read and go where it points."""
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    target = note.url
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect("members:notifications")


@login_required
@require_POST
def notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("members:notifications")
