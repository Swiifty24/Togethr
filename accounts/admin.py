from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.validators import MinLengthValidator

from .models import ActivityLog, EmailVerification, Notification, Profile, User

USERNAME_HELP = "At least 5 characters (maximum 150). Letters, numbers and @ . + - _ only."
PASSWORD_HELP = (
    "At least 8 characters, with upper and lowercase letters, a number and a symbol. "
    "Avoid common words and your name or email."
)


class TogethrHelpTextMixin:
    """Replace Django's generic admin hints with Togethr's real requirements."""

    help_texts = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, text in self.help_texts.items():
            if name in self.fields:
                self.fields[name].help_text = text


class TogethrUserCreationForm(TogethrHelpTextMixin, UserCreationForm):
    help_texts = {
        "username": USERNAME_HELP,
        "full_name": "Shown on profiles and activity pages. At least 2 characters.",
        "email": "Used for sign-in and account emails. Must be unique.",
        "email_verified": "Checked for accounts created by a trusted administrator.",
        "password1": PASSWORD_HELP,
        "password2": "Enter the same password again to confirm it.",
    }

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "full_name", "email_verified")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].validators.append(MinLengthValidator(5))
        self.fields["email_verified"].initial = True  # accounts made here are trusted
        self.fields["email"].required = True
        self.fields["full_name"].required = True


class TogethrUserChangeForm(TogethrHelpTextMixin, UserChangeForm):
    help_texts = {
        "username": USERNAME_HELP,
        "password": "Passwords are stored hashed and can't be viewed. Use the change-password form to set a new one.",
        "full_name": "Shown on profiles and activity pages. At least 2 characters.",
        "email": "Used for sign-in and account emails. Must be unique.",
        "email_verified": "Unverified accounts cannot sign in until the email code is confirmed.",
        "is_active": "Uncheck to block sign-in without deleting the account.",
        "is_staff": "Allows access to this Django admin site. Super Administrators get this automatically.",
        "is_superuser": "Full access: Admin Home (/manage/) and management of every account.",
        "groups": "Django permission groups. Togethr uses roles, so leave this empty unless needed.",
        "user_permissions": "Individual Django permissions; normally covered by the Super Administrator role.",
        "last_login": "Last time this account signed in.",
        "date_joined": "When this account was created.",
    }

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].validators.append(MinLengthValidator(5))


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = TogethrUserChangeForm
    add_form = TogethrUserCreationForm
    inlines = [ProfileInline]
    list_display = ("username", "full_name", "email", "email_verified", "is_active", "is_superuser", "date_joined")
    list_filter = ("is_superuser", "is_active", "email_verified")
    search_fields = ("username", "full_name", "email")
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("full_name", "email")}),
        ("Status", {"fields": ("email_verified", "is_active")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "full_name", "email", "email_verified", "password1", "password2"),
        }),
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "user", "actor", "identifier", "ip_address")
    list_filter = ("action",)
    search_fields = ("identifier", "description", "user__username")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "attempts", "consumed_at")
    exclude = ("code_hash",)
    readonly_fields = ("user", "created_at", "expires_at", "attempts", "consumed_at")

    def has_add_permission(self, request):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")
