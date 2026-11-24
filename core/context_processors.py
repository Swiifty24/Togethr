from django.conf import settings


def site(request):
    context = {"SITE_NAME": settings.SITE_NAME}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from activities.models import Activity, Participation

        context["unread_notifications"] = user.notifications.filter(is_read=False).count()
        context["pending_invitations"] = Participation.objects.filter(
            user=user, response=Participation.INVITED, activity__status__in=Activity.OPEN_STATUSES
        ).count()
    return context
