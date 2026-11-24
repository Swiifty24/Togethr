from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.conf import settings

from .models import User
from .services import is_login_locked
from .utils import get_client_ip


class StyledFormMixin:
    """Adds Togethr's CSS classes to every widget."""

    def style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "checkbox")
            elif isinstance(widget, forms.RadioSelect):
                pass
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "input select")
            else:
                widget.attrs.setdefault("class", "input")


def find_user(identifier):
    """Look a user up by username or e-mail, case-insensitively."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    return (
        User.objects.filter(username__iexact=identifier).first()
        or User.objects.filter(email__iexact=identifier).first()
    )


class RegistrationForm(StyledFormMixin, forms.Form):
    full_name = forms.CharField(
        label="Full name", max_length=150, validators=[MinLengthValidator(2)],
        widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Jessa Flores"}),
    )
    username = forms.CharField(
        label="Username", max_length=150, validators=[MinLengthValidator(3)],
        help_text="Letters, numbers and @ . + - _ only.",
        widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "jessaflores"}),
    )
    email = forms.EmailField(
        label="Email address", max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@gmail.com"}),
    )
    password1 = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-input": ""}),
    )
    password2 = forms.CharField(
        label="Confirm password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-confirm": ""}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].validators.extend(User._meta.get_field("username").validators)
        self.style_fields()

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An account with this email address already exists. "
                "If you haven't verified it yet, log in and we'll send you a new code."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        password1, password2 = cleaned.get("password1"), cleaned.get("password2")
        if password1:
            candidate = User(
                username=cleaned.get("username", ""),
                email=cleaned.get("email", ""),
                full_name=cleaned.get("full_name", ""),
            )
            try:
                password_validation.validate_password(password1, candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two passwords don't match.")
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = User(
            username=data["username"], email=data["email"], full_name=data["full_name"],
            is_active=False, email_verified=False,  # inactive until the e-mail code is confirmed
        )
        user.set_password(data["password1"])
        user.save()
        return user


class VerificationCodeForm(StyledFormMixin, forms.Form):
    code = forms.RegexField(
        regex=r"^\d{6}$", label="Verification code", strip=True,
        error_messages={"invalid": "Enter the 6-digit code from your email."},
        widget=forms.TextInput(attrs={
            "inputmode": "numeric", "autocomplete": "one-time-code", "maxlength": "6",
            "placeholder": "000000", "pattern": "[0-9]{6}", "data-code-input": "",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields["code"].widget.attrs["class"] = "input code-input"


class LoginForm(StyledFormMixin, forms.Form):
    identifier = forms.CharField(
        label="Username or email", max_length=254,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    remember_me = forms.BooleanField(label="Remember me", required=False)

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None
        self.unverified_user = None
        self.failed_credentials = False
        self.style_fields()

    def clean(self):
        cleaned = super().clean()
        identifier, password = cleaned.get("identifier"), cleaned.get("password")
        if not identifier or not password:
            return cleaned

        ip = get_client_ip(self.request) if self.request else None
        if is_login_locked(identifier.strip().lower(), ip):
            raise ValidationError(
                "Too many failed attempts. Please wait %(minutes)s minutes and try again.",
                code="locked", params={"minutes": settings.LOGIN_LOCKOUT_MINUTES},
            )

        user = find_user(identifier)
        if user is None:
            User().set_password(password)  # equalise timing so unknown names aren't detectable
        if user is None or not user.check_password(password):
            self.failed_credentials = True
            raise ValidationError("Incorrect username/email or password.", code="invalid_login")

        # Password is correct from here on, so it is safe to explain account state.
        if not user.email_verified:
            self.unverified_user = user
            raise ValidationError("Please verify your email address before signing in.", code="unverified")
        if not user.is_active:
            raise ValidationError(
                "This account has been deactivated. Contact an administrator for help.", code="inactive"
            )
        self.user = user
        return cleaned


class PasswordResetRequestForm(StyledFormMixin, PasswordResetForm):
    email = forms.EmailField(
        label="Email address", max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True, "placeholder": "you@gmail.com"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class PasswordResetConfirmForm(StyledFormMixin, SetPasswordForm):
    """Django's SetPasswordForm already runs every validator in AUTH_PASSWORD_VALIDATORS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields["new_password1"].widget.attrs["data-password-input"] = ""
        self.fields["new_password2"].widget.attrs["data-password-confirm"] = ""
