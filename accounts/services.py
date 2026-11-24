"""Business logic for verification codes, rate limiting, logging and notifications."""
import logging
import secrets
import smtplib
from datetime import timedelta
from math import ceil

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import ActivityLog, EmailVerification, Notification
from .utils import get_client_ip

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Activity log & notifications
# --------------------------------------------------------------------------
def log_activity(action, *, user=None, actor=None, description="", request=None, identifier="", ip=None):
    if request is not None and ip is None:
        ip = get_client_ip(request)
    return ActivityLog.objects.create(
        user=user, actor=actor, action=action, description=description[:255],
        identifier=(identifier or "")[:254], ip_address=ip,
    )


def notify(user, title, message="", level=Notification.INFO, url=""):
    return Notification.objects.create(user=user, title=title[:120], message=message[:255], level=level, url=url[:255])


# --------------------------------------------------------------------------
# Email verification codes
# --------------------------------------------------------------------------
class VerificationError(Exception):
    """The submitted code could not be accepted; ``message`` is user-facing."""

    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


class ResendThrottled(Exception):
    def __init__(self, wait_seconds, hourly=False):
        super().__init__(f"Wait {wait_seconds}s")
        self.wait_seconds = wait_seconds
        self.hourly = hourly


class EmailSendError(Exception):
    pass


def generate_code():
    """Cryptographically secure six-digit code."""
    return f"{secrets.randbelow(10 ** 6):06d}"


def hash_code(user_id, code):
    # Keyed with SECRET_KEY and bound to the user, so a leaked table is useless
    # and one user's code can never validate another user's account.
    return salted_hmac("togethr.email-verification", f"{user_id}:{code}", algorithm="sha256").hexdigest()


def resend_wait_seconds(user):
    """Seconds left before another code may be requested (0 = allowed now)."""
    last = user.verifications.order_by("-created_at").first()
    if not last:
        return 0
    elapsed = (timezone.now() - last.created_at).total_seconds()
    return max(0, ceil(settings.VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed))


def send_verification_email(user, code):
    context = {
        "user": user,
        "code": code,
        "minutes": settings.VERIFICATION_CODE_TTL_MINUTES,
        "site_name": settings.SITE_NAME,
    }
    message = EmailMultiAlternatives(
        subject=f"{code} is your {settings.SITE_NAME} verification code",
        body=render_to_string("emails/verification_code.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(render_to_string("emails/verification_code.html", context), "text/html")
    try:
        message.send(fail_silently=False)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Could not send verification email to user %s: %s", user.pk, exc)
        raise EmailSendError(str(exc)) from exc


def issue_verification_code(user, request=None):
    """
    Create and e-mail a fresh code, invalidating every earlier one.
    Raises ResendThrottled (cooldown / hourly cap) or EmailSendError.
    """
    now = timezone.now()
    wait = resend_wait_seconds(user)
    if wait:
        raise ResendThrottled(wait)
    sent_last_hour = user.verifications.filter(created_at__gte=now - timedelta(hours=1)).count()
    if sent_last_hour >= settings.VERIFICATION_MAX_SENDS_PER_HOUR:
        raise ResendThrottled(0, hourly=True)

    code = generate_code()
    with transaction.atomic():
        user.verifications.filter(consumed_at__isnull=True).update(consumed_at=now)
        verification = EmailVerification.objects.create(
            user=user,
            code_hash=hash_code(user.pk, code),
            created_at=now,
            expires_at=now + timedelta(minutes=settings.VERIFICATION_CODE_TTL_MINUTES),
        )
    try:
        send_verification_email(user, code)
    except EmailSendError:
        verification.delete()  # a failed send must not eat the user's quota
        raise
    log_activity(ActivityLog.VERIFICATION_SENT, user=user, request=request, description="Verification code sent")
    return verification


def verify_code(user, submitted_code):
    """
    Check a code for ``user``. On success the account is verified and activated.
    Raises VerificationError otherwise. State changes (attempt counts, locking)
    are committed *before* the error is raised.
    """
    submitted_code = (submitted_code or "").strip()
    error = None
    with transaction.atomic():
        verification = (
            EmailVerification.objects.select_for_update()
            .filter(user=user, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        now = timezone.now()
        if verification is None:
            error = VerificationError("There is no active code. Request a new one.", "none")
        elif verification.is_expired:
            verification.consumed_at = now
            verification.save(update_fields=["consumed_at"])
            error = VerificationError("This code has expired. Request a new one.", "expired")
        elif verification.attempts >= settings.VERIFICATION_MAX_ATTEMPTS:
            verification.consumed_at = now
            verification.save(update_fields=["consumed_at"])
            error = VerificationError("Too many incorrect attempts. Request a new code.", "locked")
        elif not constant_time_compare(verification.code_hash, hash_code(user.pk, submitted_code)):
            verification.attempts += 1
            remaining = settings.VERIFICATION_MAX_ATTEMPTS - verification.attempts
            if remaining <= 0:
                verification.consumed_at = now
                error = VerificationError("Too many incorrect attempts. Request a new code.", "locked")
            else:
                plural = "" if remaining == 1 else "s"
                error = VerificationError(f"That code isn't right. {remaining} attempt{plural} left.", "incorrect")
            verification.save(update_fields=["attempts", "consumed_at"])
        else:
            verification.consumed_at = now
            verification.save(update_fields=["consumed_at"])
            user.email_verified = True
            user.is_active = True
            user.save(update_fields=["email_verified", "is_active"])
    if error:
        raise error


# --------------------------------------------------------------------------
# Rate limiting (backed by the activity log, so it works across processes)
# --------------------------------------------------------------------------
def is_login_locked(identifier, ip):
    since = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    failures = ActivityLog.objects.filter(action=ActivityLog.LOGIN_FAILED, created_at__gte=since)
    if failures.filter(identifier=identifier, ip_address=ip).count() >= settings.LOGIN_MAX_ATTEMPTS:
        return True
    return failures.filter(ip_address=ip).count() >= settings.LOGIN_MAX_ATTEMPTS_PER_IP


def password_reset_throttled(email, ip):
    since = timezone.now() - timedelta(hours=1)
    recent = ActivityLog.objects.filter(action=ActivityLog.PASSWORD_RESET_REQUESTED, created_at__gte=since)
    limit = settings.PASSWORD_RESET_MAX_REQUESTS_PER_HOUR
    return recent.filter(identifier=email).count() >= limit or recent.filter(ip_address=ip).count() >= limit * 4
