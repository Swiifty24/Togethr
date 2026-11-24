from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone


class UserManager(DjangoUserManager):
    """
    Accounts created through the manager (``createsuperuser``, shell, scripts,
    the administrator pages) are trusted and count as e-mail verified.
    Self-registration goes through the registration form instead, which creates
    an inactive, unverified user until the e-mail code is confirmed.
    """

    def _create_user(self, username, email, password, **extra_fields):
        extra_fields.setdefault("email_verified", True)
        return super()._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user (set up at project start, as Django recommends).

    Roles:
      * Super Administrator -> ``is_superuser`` (and ``is_staff``)
      * Regular user        -> everyone else
    """

    ROLE_SUPERADMIN = "super_admin"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [
        (ROLE_MEMBER, "Regular user"),
        (ROLE_SUPERADMIN, "Super Administrator"),
    ]

    first_name = None  # replaced by a single full_name field
    last_name = None

    full_name = models.CharField(max_length=150)
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "An account with this email address already exists."},
    )
    email_verified = models.BooleanField(default=False)

    objects = UserManager()

    REQUIRED_FIELDS = ["email", "full_name"]

    class Meta:
        ordering = ["-date_joined"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    # --- naming -------------------------------------------------------------
    def get_full_name(self):
        return self.full_name or self.username

    def get_short_name(self):
        return self.get_full_name().split()[0]

    @property
    def initials(self):
        parts = self.get_full_name().split()
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    # --- role & status ------------------------------------------------------
    @property
    def role(self):
        return self.ROLE_SUPERADMIN if self.is_superuser else self.ROLE_MEMBER

    @property
    def role_label(self):
        return dict(self.ROLE_CHOICES)[self.role]

    @property
    def status(self):
        if not self.email_verified:
            return "unverified"
        return "active" if self.is_active else "inactive"

    @property
    def status_label(self):
        return {"unverified": "Unverified", "inactive": "Deactivated", "active": "Active"}[self.status]


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(max_length=300, blank=True)
    location = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class EmailVerification(models.Model):
    """A one-time e-mail code. Only a keyed hash of the code is stored."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="verifications")
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    # Set when the code was used OR invalidated (replaced, expired, locked).
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"Verification for {self.user_id} at {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_usable(self):
        return (
            self.consumed_at is None
            and not self.is_expired
            and self.attempts < settings.VERIFICATION_MAX_ATTEMPTS
        )


class ActivityLog(models.Model):
    REGISTERED = "registered"
    VERIFICATION_SENT = "verification_sent"
    EMAIL_VERIFIED = "email_verified"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET = "password_reset"
    PROFILE_UPDATED = "profile_updated"
    ADMIN_USER_CREATED = "admin_user_created"
    ADMIN_USER_UPDATED = "admin_user_updated"
    ADMIN_ROLE_CHANGED = "admin_role_changed"
    ADMIN_USER_ACTIVATED = "admin_user_activated"
    ADMIN_USER_DEACTIVATED = "admin_user_deactivated"
    ADMIN_USER_DELETED = "admin_user_deleted"

    ACTION_CHOICES = [
        (REGISTERED, "Registered"),
        (VERIFICATION_SENT, "Verification code sent"),
        (EMAIL_VERIFIED, "Email verified"),
        (LOGIN, "Signed in"),
        (LOGIN_FAILED, "Failed sign-in"),
        (LOGOUT, "Signed out"),
        (PASSWORD_CHANGED, "Password changed"),
        (PASSWORD_RESET_REQUESTED, "Password reset requested"),
        (PASSWORD_RESET, "Password reset"),
        (PROFILE_UPDATED, "Profile updated"),
        (ADMIN_USER_CREATED, "Account created by admin"),
        (ADMIN_USER_UPDATED, "Account edited by admin"),
        (ADMIN_ROLE_CHANGED, "Role changed by admin"),
        (ADMIN_USER_ACTIVATED, "Account activated by admin"),
        (ADMIN_USER_DEACTIVATED, "Account deactivated by admin"),
        (ADMIN_USER_DELETED, "Account deleted by admin"),
    ]
    SECURITY_ACTIONS = [
        LOGIN, LOGIN_FAILED, LOGOUT, PASSWORD_CHANGED, PASSWORD_RESET_REQUESTED, PASSWORD_RESET,
        EMAIL_VERIFIED,
    ]

    # The account the event is about (kept as NULL if that account is later deleted).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities"
    )
    # Who performed it (differs from ``user`` for administrator actions).
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="actions_performed"
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    identifier = models.CharField(max_length=254, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_action_display()} ({self.created_at:%Y-%m-%d %H:%M})"


class Notification(models.Model):
    INFO, SUCCESS, WARNING = "info", "success", "warning"
    LEVEL_CHOICES = [(INFO, "Info"), (SUCCESS, "Success"), (WARNING, "Warning")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=255, blank=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=INFO)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
