from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import ActivityLog, EmailVerification, Notification, Profile, User


class TogethrUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "full_name", "email_verified")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email_verified"].initial = True  # accounts made here are trusted
        self.fields["email"].required = True
        self.fields["full_name"].required = True


class TogethrUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


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
            "fields": ("username", "full_name", "email", "email_verified", "usable_password", "password1", "password2"),
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
