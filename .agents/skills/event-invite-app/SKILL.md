---
name: event-invite-app
description: "Use when building any website with events, invitations, RSVPs, bookings, or sign-ups, such as party invites, meetups, classes, appointments, or volunteer shifts."
---

# Event and invitation websites

## Ask first
Who can create events? Who can see them (invited only, link, everyone)? Do people reply
or book a slot? Is there a capacity, minimum, or waitlist? Does money change hands? If
yes, use a payment provider; never build payments yourself.

## Types
- Social invites: private, RSVP, invite friends, share link
- Public events: discovery page, search, registration
- Booking: time slots, no double booking, cancellations
- Volunteer: capacity per shift, check-in

## Data model (Django)
    class Event(models.Model):
        host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="hosted_events")
        title = models.CharField(max_length=120)
        description = models.TextField(blank=True)
        starts_at = models.DateTimeField()
        ends_at = models.DateTimeField()
        location = models.CharField(max_length=200, blank=True)
        visibility = models.CharField(max_length=10, default="private")
        capacity = models.PositiveIntegerField(null=True, blank=True)
        min_attendees = models.PositiveIntegerField(default=1)
        is_cancelled = models.BooleanField(default=False)
        share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

        @property
        def status(self):  # computed, never stored
            if self.is_cancelled:
                return "cancelled"
            going = self.rsvps.filter(status="going").count()
            return "confirmed" if going >= self.min_attendees else "pending"

    class RSVP(models.Model):  # statuses: invited, going, maybe, declined, waitlisted
        event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
        user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
        status = models.CharField(max_length=10, default="invited")
        class Meta:
            constraints = [models.UniqueConstraint(fields=["event", "user"],
                                                   name="one_rsvp_per_user_per_event")]

Add a Notification model (user, message, is_read, created_at) for invites, changes,
and cancellations.

## Rules that prevent bugs
- Time zones: USE_TZ = True, a real TIME_ZONE, and timezone.now(), never datetime.now().
- Capacity races: wrap check and save in transaction.atomic() with select_for_update().
  SQLite ignores that lock, so it only protects PostgreSQL or MySQL.
- One reply per person: use update_or_create so changing a reply makes no second row.
- Cancel with is_cancelled = True and notify guests; do not hard-delete by default.
- Block new RSVPs after the event starts. Validate that ends_at is after starts_at.
- Share links use share_token, never the numeric id.
- Every list needs an empty state.