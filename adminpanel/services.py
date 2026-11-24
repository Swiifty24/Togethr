from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog, User


def user_stats():
    return User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(email_verified=True, is_active=True)),
        unverified=Count("id", filter=Q(email_verified=False)),
        inactive=Count("id", filter=Q(email_verified=True, is_active=False)),
        admins=Count("id", filter=Q(is_superuser=True, is_active=True)),
    )


def registrations_last_days(days=7):
    """[(date, count), …] for the last N days, oldest first, zero-filled."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        User.objects.filter(date_joined__date__gte=start)
        .annotate(day=TruncDate("date_joined"))
        .values("day").annotate(n=Count("id"))
    )
    counts = {row["day"]: row["n"] for row in rows}
    return [(start + timedelta(days=i), counts.get(start + timedelta(days=i), 0)) for i in range(days)]


def system_alerts(stats):
    """Important notices for administrators, derived from live data."""
    alerts = []
    now = timezone.now()
    stale = User.objects.filter(email_verified=False, date_joined__lt=now - timedelta(days=1)).count()
    if stale:
        alerts.append({
            "level": "warning", "title": f"{stale} account{'s' if stale != 1 else ''} waiting over a day for email verification",
            "detail": "They may have mistyped their address. You can verify or delete them.",
            "url": reverse("adminpanel:user_list") + "?status=unverified",
        })
    failed = ActivityLog.objects.filter(action=ActivityLog.LOGIN_FAILED, created_at__gte=now - timedelta(hours=1)).count()
    if failed >= 10:
        alerts.append({
            "level": "warning", "title": f"{failed} failed sign-in attempts in the last hour",
            "detail": "This could be someone guessing passwords. Review the activity log below.", "url": "",
        })
    if stats["admins"] <= 1:
        alerts.append({
            "level": "info", "title": "Only one Super Administrator",
            "detail": "Consider adding a second one so you can't be locked out.", "url": "",
        })
    return alerts
