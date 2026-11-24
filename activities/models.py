from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class ActivityQuerySet(models.QuerySet):
    def with_counts(self):
        return self.annotate(
            joined_count=Count("participations", filter=Q(participations__response="join"), distinct=True)
        )

    def discoverable(self):
        return self.filter(visibility=Activity.PUBLIC, status__in=[Activity.PENDING, Activity.CONFIRMED])


class Activity(models.Model):
    PENDING, CONFIRMED, CANCELED, COMPLETED = "pending", "confirmed", "canceled", "completed"
    STATUS_CHOICES = [
        (PENDING, "Pending"), (CONFIRMED, "Confirmed"), (CANCELED, "Canceled"), (COMPLETED, "Completed"),
    ]
    OPEN_STATUSES = (PENDING, CONFIRMED)
    PUBLIC, INVITE_ONLY = "public", "invite_only"
    VISIBILITY_CHOICES = [
        (PUBLIC, "Public: anyone on Togethr can find and join it"),
        (INVITE_ONLY, "Invite only: only people you invite can see it"),
    ]

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organized_activities")
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=2000)
    cover_image = models.ImageField(
        upload_to="activity_covers/", blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp", "gif"])],
    )
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200)
    min_participants = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    max_participants = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    visibility = models.CharField(max_length=12, choices=VISIBILITY_CHOICES, default=PUBLIC)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActivityQuerySet.as_manager()

    class Meta:
        ordering = ["date", "start_time"]
        indexes = [models.Index(fields=["status", "date"])]
        verbose_name_plural = "activities"

    def __str__(self):
        return self.title

    # --- schedule ---
    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    @property
    def ends_at(self):
        if self.end_time:
            end = timezone.make_aware(datetime.combine(self.date, self.end_time))
            if end > self.starts_at:
                return end
        return self.starts_at + timedelta(hours=3)

    @property
    def has_ended(self):
        return timezone.now() >= self.ends_at

    @property
    def is_open(self):
        """Still possible to respond to / join."""
        return self.status in self.OPEN_STATUSES and not self.has_ended

    # --- people ---
    @property
    def join_count(self):
        cached = getattr(self, "joined_count", None)
        return cached if cached is not None else self.participations.filter(response=Participation.JOIN).count()

    @property
    def spots_left(self):
        if self.max_participants is None:
            return None
        return max(self.max_participants - self.join_count, 0)

    @property
    def is_full(self):
        return self.max_participants is not None and self.join_count >= self.max_participants

    @property
    def still_needed(self):
        return max(self.min_participants - self.join_count, 0)

    @property
    def progress_pct(self):
        return min(100, round(self.join_count / self.min_participants * 100)) if self.min_participants else 100

    @property
    def placeholder_index(self):
        return (self.category_id or 0) % 6


class Participation(models.Model):
    """One person's relationship to an activity: invited, or one of the three responses."""

    INVITED, JOIN, CANT_JOIN, NOT_SURE = "invited", "join", "cant_join", "not_sure"
    RESPONSE_CHOICES = [
        (INVITED, "Waiting for reply"), (JOIN, "Joined"), (CANT_JOIN, "Can't join"), (NOT_SURE, "Not sure"),
    ]
    ANSWERS = (JOIN, CANT_JOIN, NOT_SURE)

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="participations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations")
    response = models.CharField(max_length=10, choices=RESPONSE_CHOICES, default=INVITED, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_invitations"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["activity", "user"], name="one_participation_per_user")]

    def __str__(self):
        return f"{self.user_id} -> {self.activity_id}: {self.response}"
