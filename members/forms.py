from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator

from accounts.forms import StyledFormMixin, identifier_taken
from accounts.models import User


class ProfileForm(StyledFormMixin, forms.Form):
    full_name = forms.CharField(label="Full name", max_length=150, validators=[MinLengthValidator(2)])
    username = forms.CharField(label="Username", max_length=150, validators=[MinLengthValidator(5)],
                               help_text="At least 5 characters. Letters, numbers and @ . + - _ only.")
    location = forms.CharField(label="Location", max_length=100, required=False,
                               widget=forms.TextInput(attrs={"placeholder": "City, Country"}))
    avatar = forms.ImageField(label="Profile picture", required=False,
                              help_text="JPG, PNG or WebP, up to 3 MB.",
                              widget=forms.FileInput(attrs={"accept": "image/*"}))
    remove_avatar = forms.BooleanField(label="Remove my current picture", required=False)
    bio = forms.CharField(label="About you", max_length=300, required=False,
                          widget=forms.Textarea(attrs={"rows": 4, "placeholder": "A line or two about yourself"}))

    def __init__(self, *args, user, **kwargs):
        self.user = user
        initial = {
            "full_name": user.full_name, "username": user.username,
            "location": user.profile.location, "bio": user.profile.bio,
        }
        kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)
        self.fields["username"].validators.extend(User._meta.get_field("username").validators)
        self.style_fields()

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())

    def clean_avatar(self):
        image = self.cleaned_data.get("avatar")
        if image and image.size > 3 * 1024 * 1024:
            raise ValidationError("Please choose an image under 3 MB.")
        return image

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if identifier_taken(username, exclude_pk=self.user.pk):
            raise ValidationError(
                "That username is already taken or is another account's email address."
            )
        return username

    def save(self):
        data = self.cleaned_data
        self.user.full_name = data["full_name"]
        self.user.username = data["username"]
        self.user.save(update_fields=["full_name", "username"])
        profile = self.user.profile
        profile.location = data["location"].strip()
        profile.bio = data["bio"].strip()
        if data.get("avatar"):
            profile.avatar = data["avatar"]
        elif data.get("remove_avatar"):
            profile.avatar = ""
        profile.save()
        return self.user


class ChangePasswordForm(StyledFormMixin, PasswordChangeForm):
    """Django's PasswordChangeForm: checks the old password and runs every password validator."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["data-password-input"] = ""
        self.fields["new_password2"].widget.attrs["data-password-confirm"] = ""
