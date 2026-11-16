from django.contrib import admin

# ── Admin Site Customization ──────────────────────────────────────────
admin.site.site_header = "TOGETHR Admin"
admin.site.site_title = "TOGETHR Admin Portal"
admin.site.index_title = "Welcome to TOGETHR Administration"


# ── Model Admin Registrations ─────────────────────────────────────────
# When Activity, Participation / RSVP, or Notification models are created in models.py,
# they will automatically register here with optimized list views and filters.

try:
    from .models import Activity

    @admin.register(Activity)
    class ActivityAdmin(admin.ModelAdmin):
        list_display = ("title", "creator", "date", "status")
        list_filter = ("status", "date")
        search_fields = ("title", "creator__username", "location")
        date_hierarchy = "date"
        list_select_related = ("creator",)
        readonly_fields = ("share_token", "created_at", "updated_at")
        actions = ["cancel_selected_activities"]

        @admin.action(description="Cancel selected activities")
        def cancel_selected_activities(self, request, queryset):
            # Check model field compatibility (status or is_cancelled)
            if hasattr(queryset.model, "status"):
                updated = queryset.update(status="cancelled")
            elif hasattr(queryset.model, "is_cancelled"):
                updated = queryset.update(is_cancelled=True)
            else:
                updated = 0
            self.message_user(request, f"{updated} activity/activities cancelled.")
except (ImportError, AttributeError):
    # Activity model not yet defined in models.py
    pass


try:
    from .models import Participation

    @admin.register(Participation)
    class ParticipationAdmin(admin.ModelAdmin):
        list_display = ("user", "activity", "status", "created_at")
        list_filter = ("status",)
        search_fields = ("user__username", "activity__title")
        list_select_related = ("user", "activity")
except (ImportError, AttributeError):
    # Participation model not yet defined in models.py
    pass


try:
    from .models import RSVP

    @admin.register(RSVP)
    class RSVPAdmin(admin.ModelAdmin):
        list_display = ("user", "activity", "status", "created_at")
        list_filter = ("status",)
        search_fields = ("user__username", "activity__title")
        list_select_related = ("user", "activity")
except (ImportError, AttributeError):
    # RSVP model not yet defined in models.py
    pass


try:
    from .models import Notification

    @admin.register(Notification)
    class NotificationAdmin(admin.ModelAdmin):
        list_display = ("user", "message", "is_read", "created_at")
        list_filter = ("is_read", "created_at")
        search_fields = ("user__username", "message")
        list_select_related = ("user",)
except (ImportError, AttributeError):
    # Notification model not yet defined in models.py
    pass
