from django.conf import settings
from django.db.models import Count, Q


def site(request):
    context = {"SITE_NAME": settings.SITE_NAME}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from accounts.models import User
        from activities.models import Activity, Participation

        # One query for both nav badges instead of two separate counts.
        counts = User.objects.filter(pk=user.pk).annotate(
            unread=Count("notifications", filter=Q(notifications__is_read=False), distinct=True),
            invited=Count(
                "participations",
                filter=Q(
                    participations__response=Participation.INVITED,
                    participations__activity__status__in=Activity.OPEN_STATUSES,
                ),
                distinct=True,
            ),
        ).values("unread", "invited").first()
        context["unread_notifications"] = counts["unread"] if counts else 0
        context["pending_invitations"] = counts["invited"] if counts else 0
    return context
