"""Activity rules: responses, minimum/maximum checks, status changes and notifications."""
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification, User
from accounts.services import notify

from .models import Activity, Participation


class ActivityError(Exception):
    """A rule was broken; the message is safe to show to the user."""


def activity_url(activity):
    return reverse("activities:detail", args=[activity.pk])


def sync_statuses():
    """Finished activities become Completed (if Confirmed) or Canceled (if never reached the minimum)."""
    today = timezone.localdate()
    now = timezone.now()
    for activity in Activity.objects.filter(status__in=Activity.OPEN_STATUSES, date__lte=today):
        if activity.ends_at <= now:
            if activity.status == Activity.CONFIRMED:
                activity.status = Activity.COMPLETED
            else:
                activity.status = Activity.CANCELED
                activity.canceled_at = now
            activity.save(update_fields=["status", "canceled_at", "updated_at"])


def _joined_users(activity):
    return User.objects.filter(participations__activity=activity, participations__response=Participation.JOIN)


def recalculate_status(activity):
    """Compare Joined count with the minimum and move Pending <-> Confirmed, notifying people."""
    if activity.status not in Activity.OPEN_STATUSES:
        return
    joined = activity.participations.filter(response=Participation.JOIN).count()
    url = activity_url(activity)
    if activity.status == Activity.PENDING and joined >= activity.min_participants:
        activity.status = Activity.CONFIRMED
        activity.save(update_fields=["status", "updated_at"])
        text = f"Enough people joined “{activity.title}”. It's on!"
        notify(activity.organizer, "Activity confirmed", text, Notification.SUCCESS, url)
        for person in _joined_users(activity):
            notify(person, "Activity confirmed", text, Notification.SUCCESS, url)
    elif activity.status == Activity.CONFIRMED and joined < activity.min_participants:
        activity.status = Activity.PENDING
        activity.save(update_fields=["status", "updated_at"])
        notify(
            activity.organizer, "Back to pending",
            f"“{activity.title}” dropped below {activity.min_participants} people ({joined} joined).",
            Notification.WARNING, url,
        )


@transaction.atomic
def set_response(activity_id, user, response):
    """Join / Can't Join / Not Sure. Used by the Join button and by invitations."""
    if response not in Participation.ANSWERS:
        raise ActivityError("That isn't a valid response.")
    activity = Activity.objects.select_for_update().get(pk=activity_id)
    if activity.organizer_id == user.pk:
        raise ActivityError("You're the organizer of this activity.")
    if not activity.is_open:
        raise ActivityError("This activity is no longer open for responses.")
    participation = Participation.objects.filter(activity=activity, user=user).first()
    if participation is None and activity.visibility != Activity.PUBLIC:
        raise ActivityError("This activity is invite only.")
    already_joined = participation is not None and participation.response == Participation.JOIN
    if response == Participation.JOIN and not already_joined and activity.is_full:
        raise ActivityError("Sorry, this activity is already full.")
    previous = participation.response if participation else None
    if participation is None:
        participation = Participation.objects.create(activity=activity, user=user, response=response)
    elif participation.response != response:
        participation.response = response
        participation.save(update_fields=["response", "updated_at"])
    if previous != response:
        verb = {
            Participation.JOIN: "is going to", Participation.CANT_JOIN: "can't join",
            Participation.NOT_SURE: "is not sure about",
        }[response]
        notify(activity.organizer, "New response", f"{user.get_full_name()} {verb} “{activity.title}”.",
               Notification.INFO, reverse("activities:participants", args=[activity.pk]))
    recalculate_status(activity)
    return participation


@transaction.atomic
def leave_activity(activity_id, user):
    activity = Activity.objects.select_for_update().get(pk=activity_id)
    participation = Participation.objects.filter(activity=activity, user=user).first()
    if participation is None or participation.response != Participation.JOIN:
        raise ActivityError("You haven't joined this activity.")
    if not activity.is_open:
        raise ActivityError("This activity is no longer open for changes.")
    if participation.invited_by_id:
        participation.response = Participation.CANT_JOIN
        participation.save(update_fields=["response", "updated_at"])
    else:
        participation.delete()
    notify(activity.organizer, "Someone left", f"{user.get_full_name()} left “{activity.title}”.",
           Notification.WARNING, reverse("activities:participants", args=[activity.pk]))
    recalculate_status(activity)


@transaction.atomic
def invite_users(activity, organizer, users):
    created = 0
    for person in users:
        if person.pk == organizer.pk:
            continue
        _, was_new = Participation.objects.get_or_create(
            activity=activity, user=person, defaults={"response": Participation.INVITED, "invited_by": organizer}
        )
        if was_new:
            created += 1
            notify(person, "You're invited!", f"{organizer.get_full_name()} invited you to “{activity.title}”.",
                   Notification.INFO, activity_url(activity))
    return created


@transaction.atomic
def remove_participant(activity, participation):
    person = participation.user
    was_joined = participation.response == Participation.JOIN
    participation.delete()
    notify(person, "Removed from activity", f"You're no longer part of “{activity.title}”.",
           Notification.WARNING, activity_url(activity))
    if was_joined:
        recalculate_status(activity)


@transaction.atomic
def cancel_activity(activity, actor):
    if activity.status not in Activity.OPEN_STATUSES:
        raise ActivityError("This activity can't be canceled any more.")
    activity.status = Activity.CANCELED
    activity.canceled_at = timezone.now()
    activity.save(update_fields=["status", "canceled_at", "updated_at"])
    for participation in activity.participations.select_related("user"):
        notify(participation.user, "Activity canceled", f"“{activity.title}” will no longer push through.",
               Notification.WARNING, activity_url(activity))


def notify_changes(activity, changed_labels):
    """Tell everyone involved when schedule/location/other details change."""
    if not changed_labels:
        return
    what = ", ".join(changed_labels)
    for participation in activity.participations.exclude(response=Participation.CANT_JOIN).select_related("user"):
        notify(participation.user, "Activity updated", f"The {what} of “{activity.title}” changed.",
               Notification.INFO, activity_url(activity))
