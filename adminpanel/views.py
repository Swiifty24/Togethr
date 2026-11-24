from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import superuser_required
from accounts.models import ActivityLog, User
from accounts.services import log_activity

from .forms import AdminUserForm
from .services import registrations_last_days, system_alerts, user_stats

PAGE_SIZE = 10


@superuser_required
def home(request):
    stats = user_stats()
    series = registrations_last_days(7)
    peak = max((n for _, n in series), default=0) or 1
    return render(request, "adminpanel/home.html", {
        "stats": stats,
        "alerts": system_alerts(stats),
        "recent_users": User.objects.order_by("-date_joined")[:5],
        "activities": ActivityLog.objects.select_related("user", "actor")[:10],
        "series": [{"date": d, "count": n, "pct": round(n / peak * 100)} for d, n in series],
        "series_total": sum(n for _, n in series),
    })


@superuser_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")

    users = User.objects.all()
    if q:
        users = users.filter(Q(username__icontains=q) | Q(full_name__icontains=q) | Q(email__icontains=q))
    if role == User.ROLE_SUPERADMIN:
        users = users.filter(is_superuser=True)
    elif role == User.ROLE_MEMBER:
        users = users.filter(is_superuser=False)
    if status == "active":
        users = users.filter(email_verified=True, is_active=True)
    elif status == "unverified":
        users = users.filter(email_verified=False)
    elif status == "inactive":
        users = users.filter(email_verified=True, is_active=False)

    page = Paginator(users.order_by("-date_joined"), PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "adminpanel/user_list.html", {
        "page": page, "q": q, "role": role, "status": status,
        "querystring": query.urlencode(), "total": page.paginator.count,
        "role_choices": User.ROLE_CHOICES,
    })


@superuser_required
def user_detail(request, pk):
    target = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    return render(request, "adminpanel/user_detail.html", {
        "target": target,
        "activities": target.activities.all()[:8],
        "is_self": target.pk == request.user.pk,
    })


@superuser_required
def user_create(request):
    form = AdminUserForm(request.POST or None, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_activity(ActivityLog.ADMIN_USER_CREATED, user=user, actor=request.user, request=request,
                     description=f"Account '{user.username}' created ({user.role_label})")
        messages.success(request, f"Account for {user.full_name} was created.")
        return redirect("adminpanel:user_detail", pk=user.pk)
    return render(request, "adminpanel/user_form.html", {"form": form, "target": None})


@superuser_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    before = {"role": target.role, "is_active": target.is_active}
    form = AdminUserForm(request.POST or None, instance=target, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_activity(ActivityLog.ADMIN_USER_UPDATED, user=user, actor=request.user, request=request,
                     description=f"Account '{user.username}' edited")
        if before["role"] != user.role:
            log_activity(ActivityLog.ADMIN_ROLE_CHANGED, user=user, actor=request.user, request=request,
                         description=f"Role changed to {user.role_label}")
        if before["is_active"] != user.is_active:
            action = ActivityLog.ADMIN_USER_ACTIVATED if user.is_active else ActivityLog.ADMIN_USER_DEACTIVATED
            log_activity(action, user=user, actor=request.user, request=request,
                         description=f"Account '{user.username}' {'activated' if user.is_active else 'deactivated'}")
        messages.success(request, f"{user.full_name}'s account was updated.")
        return redirect("adminpanel:user_detail", pk=user.pk)
    return render(request, "adminpanel/user_form.html", {"form": form, "target": target})


def _is_last_admin(target):
    return target.is_superuser and target.is_active and not (
        User.objects.filter(is_superuser=True, is_active=True).exclude(pk=target.pk).exists()
    )


@superuser_required
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You can't deactivate your own account.")
    elif target.is_active and _is_last_admin(target):
        messages.error(request, "At least one active Super Administrator must remain.")
    elif not target.email_verified:
        messages.error(request, "This account hasn't verified its email yet. Verify or delete it instead.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        action = ActivityLog.ADMIN_USER_ACTIVATED if target.is_active else ActivityLog.ADMIN_USER_DEACTIVATED
        word = "activated" if target.is_active else "deactivated"
        log_activity(action, user=target, actor=request.user, request=request,
                     description=f"Account '{target.username}' {word}")
        messages.success(request, f"{target.full_name}'s account was {word}.")
    return redirect("adminpanel:user_detail", pk=pk)


@superuser_required
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    blocked = None
    if target.pk == request.user.pk:
        blocked = "You can't delete your own account."
    elif _is_last_admin(target):
        blocked = "You can't delete the last active Super Administrator."
    if request.method == "POST":
        if blocked:
            messages.error(request, blocked)
            return redirect("adminpanel:user_detail", pk=pk)
        name, username = target.full_name, target.username
        target.delete()
        log_activity(ActivityLog.ADMIN_USER_DELETED, actor=request.user, request=request,
                     identifier=username, description=f"Account '{username}' deleted")
        messages.success(request, f"{name}'s account was deleted.")
        return redirect("adminpanel:user_list")
    return render(request, "adminpanel/user_confirm_delete.html", {"target": target, "blocked": blocked})
