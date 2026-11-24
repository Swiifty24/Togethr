import smtplib

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .decorators import anonymous_required
from .forms import (
    LoginForm, PasswordResetConfirmForm, PasswordResetRequestForm, RegistrationForm, VerificationCodeForm,
)
from .models import ActivityLog, Notification, User
from .services import (
    EmailSendError, ResendThrottled, VerificationError, issue_verification_code, log_activity, notify,
    password_reset_throttled, resend_wait_seconds, verify_code,
)
from .utils import get_client_ip, home_url_for, mask_email

PENDING_SESSION_KEY = "pending_verification_user_id"


def _pending_user(request):
    """The unverified account this browser session is allowed to verify (and no other)."""
    pk = request.session.get(PENDING_SESSION_KEY)
    if not pk:
        return None
    return User.objects.filter(pk=pk, email_verified=False).first()


def _send_code(request, user, *, quiet_throttle=False):
    """Issue a code and tell the user what happened. Returns True if one was sent."""
    try:
        issue_verification_code(user, request=request)
    except ResendThrottled as exc:
        if not quiet_throttle:
            if exc.hourly:
                messages.warning(request, "You've requested too many codes. Please try again in about an hour.")
            else:
                messages.warning(
                    request, f"Please wait {exc.wait_seconds} seconds before requesting another code."
                )
        return False
    except EmailSendError:
        messages.error(
            request,
            "We couldn't send the email right now. Please try “Resend code” in a moment. "
            "If this keeps happening, contact support.",
        )
        return False
    return True


@anonymous_required
def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_activity(
            ActivityLog.REGISTERED, user=user, request=request,
            description="Account registered; waiting for email verification",
        )
        request.session[PENDING_SESSION_KEY] = user.pk
        if _send_code(request, user):
            messages.success(request, f"We sent a 6-digit code to {mask_email(user.email)}.")
        return redirect("accounts:verify")
    return render(request, "accounts/register.html", {"form": form})


@anonymous_required
@never_cache
def verify_email(request):
    user = _pending_user(request)
    if user is None:
        request.session.pop(PENDING_SESSION_KEY, None)
        messages.info(request, "Sign in to continue verifying your email, or create an account.")
        return redirect("accounts:login")

    form = VerificationCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            verify_code(user, form.cleaned_data["code"])
        except VerificationError as exc:
            form.add_error("code", exc.message)
        else:
            request.session.pop(PENDING_SESSION_KEY, None)
            log_activity(ActivityLog.EMAIL_VERIFIED, user=user, request=request, description="Email verified")
            notify(
                user, "Welcome to Togethr!",
                "Your email is verified and your account is ready.", Notification.SUCCESS,
            )
            return render(request, "accounts/verify_success.html", {"verified_user": user})

    latest = user.verifications.first()
    expires_in = 0
    if latest and latest.consumed_at is None:
        expires_in = max(0, int((latest.expires_at - timezone.now()).total_seconds()))
    return render(request, "accounts/verify_email.html", {
        "form": form,
        "masked_email": mask_email(user.email),
        "expires_in": expires_in,
        "resend_wait": resend_wait_seconds(user),
    })


@anonymous_required
@require_POST
def resend_code(request):
    user = _pending_user(request)
    if user is None:
        messages.info(request, "Sign in to continue verifying your email.")
        return redirect("accounts:login")
    if _send_code(request, user):
        messages.success(request, f"A new code is on its way to {mask_email(user.email)}. Older codes no longer work.")
    return redirect("accounts:verify")


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return ""


@anonymous_required
def login_view(request):
    form = LoginForm(request.POST or None, request=request)
    if request.method == "POST":
        if form.is_valid():
            user = form.user
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            if not form.cleaned_data["remember_me"]:
                request.session.set_expiry(0)  # session ends when the browser closes
            log_activity(ActivityLog.LOGIN, user=user, request=request, description="Signed in")
            messages.success(request, f"Welcome back, {user.get_short_name()}!")
            return redirect(_safe_next(request) or home_url_for(user))

        identifier = (request.POST.get("identifier") or "").strip().lower()
        if form.failed_credentials:
            log_activity(
                ActivityLog.LOGIN_FAILED, request=request, identifier=identifier,
                description="Incorrect username/email or password",
            )
        elif form.unverified_user:
            # Correct password, but the email was never confirmed: resume verification.
            request.session[PENDING_SESSION_KEY] = form.unverified_user.pk
            if _send_code(request, form.unverified_user, quiet_throttle=True):
                messages.info(request, "Please verify your email first. We've sent you a new code.")
            else:
                messages.info(request, "Please verify your email first. Enter the code we sent you.")
            return redirect("accounts:verify")
    return render(request, "accounts/login.html", {"form": form, "next": _safe_next(request)})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_activity(ActivityLog.LOGOUT, user=request.user, request=request, description="Signed out")
    logout(request)
    messages.success(request, "You've been signed out.")
    return redirect("core:landing")


# --------------------------------------------------------------------------
# Password reset (Django's secure token mechanism, with Togethr's templates)
# --------------------------------------------------------------------------
class PasswordResetRequestView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = PasswordResetRequestForm
    email_template_name = "emails/password_reset.txt"
    html_email_template_name = "emails/password_reset.html"
    subject_template_name = "emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(home_url_for(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data["email"].strip().lower()
        ip = get_client_ip(self.request)
        if password_reset_throttled(email, ip):
            # Behave exactly as if it worked so attackers learn nothing.
            return redirect(self.success_url)
        log_activity(
            ActivityLog.PASSWORD_RESET_REQUESTED, request=self.request, identifier=email,
            description="Password reset requested",
        )
        try:
            return super().form_valid(form)
        except (smtplib.SMTPException, OSError):
            form.add_error(None, "We couldn't send the email right now. Please try again in a few minutes.")
            return self.form_invalid(form)


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = PasswordResetConfirmForm
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        log_activity(
            ActivityLog.PASSWORD_RESET, user=user, request=self.request, description="Password reset via email link"
        )
        notify(user, "Your password was reset", "If this wasn't you, contact an administrator.", Notification.WARNING)
        return response


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
