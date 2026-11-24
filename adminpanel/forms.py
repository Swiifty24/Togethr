from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator

from accounts.forms import StyledFormMixin, identifier_taken
from accounts.models import User


class AdminUserForm(StyledFormMixin, forms.Form):
    """Create / edit an account. Passes the acting admin in so it can refuse self-lockout."""

    full_name = forms.CharField(label="Full name", max_length=150, validators=[MinLengthValidator(2)])
    username = forms.CharField(label="Username", max_length=150, validators=[MinLengthValidator(5)])
    email = forms.EmailField(label="Email address", max_length=254)
    role = forms.ChoiceField(label="Role", choices=User.ROLE_CHOICES, initial=User.ROLE_MEMBER,
                             help_text="Super Administrators can manage every account and open Admin Home.")
    is_active = forms.BooleanField(label="Account is active (can sign in)", required=False, initial=True)
    email_verified = forms.BooleanField(label="Email address is verified", required=False, initial=True)
    password1 = forms.CharField(label="Password", strip=False, required=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-input": ""}))
    password2 = forms.CharField(label="Confirm password", strip=False, required=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-confirm": ""}))

    def __init__(self, *args, instance=None, acting_user=None, **kwargs):
        self.instance = instance
        self.acting_user = acting_user
        if instance is not None:
            kwargs.setdefault("initial", {
                "full_name": instance.full_name, "username": instance.username, "email": instance.email,
                "role": instance.role, "is_active": instance.is_active, "email_verified": instance.email_verified,
            })
        super().__init__(*args, **kwargs)
        self.fields["username"].validators.extend(User._meta.get_field("username").validators)
        if instance is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].help_text = "Leave blank to keep the current password."
        self.style_fields()

    def _others(self):
        qs = User.objects.all()
        return qs.exclude(pk=self.instance.pk) if self.instance else qs

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if identifier_taken(username, exclude_pk=self.instance.pk if self.instance else None):
            raise ValidationError(
                "That username is already taken or is another account's email address."
            )
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if identifier_taken(email, exclude_pk=self.instance.pk if self.instance else None):
            raise ValidationError("Another account already uses this email address or username.")
        return email

    def clean(self):
        cleaned = super().clean()
        pw1, pw2 = cleaned.get("password1"), cleaned.get("password2")
        if pw1 or pw2:
            if pw1 != pw2:
                self.add_error("password2", "The two passwords don't match.")
            else:
                candidate = self.instance or User(
                    username=cleaned.get("username", ""), email=cleaned.get("email", ""),
                    full_name=cleaned.get("full_name", ""),
                )
                try:
                    password_validation.validate_password(pw1, candidate)
                except ValidationError as exc:
                    self.add_error("password1", exc)

        # Guard rails: an admin must not lock themselves (or everyone) out.
        if self.instance and self.instance.is_superuser:
            demoting = cleaned.get("role") != User.ROLE_SUPERADMIN
            deactivating = not cleaned.get("is_active")
            if self.acting_user and self.instance.pk == self.acting_user.pk:
                if demoting:
                    self.add_error("role", "You can't remove your own Super Administrator role.")
                if deactivating:
                    self.add_error("is_active", "You can't deactivate your own account.")
            elif (demoting or deactivating) and self.instance.is_active:
                others = User.objects.filter(is_superuser=True, is_active=True).exclude(pk=self.instance.pk)
                if not others.exists():
                    self.add_error(None, "At least one active Super Administrator must remain.")
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = self.instance or User()
        user.full_name = data["full_name"]
        user.username = data["username"]
        user.email = data["email"]
        user.is_active = data["is_active"]
        user.email_verified = data["email_verified"]
        user.is_superuser = user.is_staff = data["role"] == User.ROLE_SUPERADMIN
        if data["password1"]:
            user.set_password(data["password1"])
        user.save()
        return user
