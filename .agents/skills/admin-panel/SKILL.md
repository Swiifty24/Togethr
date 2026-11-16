---
name: admin-panel
description: "Use when a website needs an admin area, staff roles, moderation, reports, exports, or a dashboard. Covers Django admin, permissions, safe deletion, and custom staff pages."
---

# Admin areas

## Choose the tool
Staff managing data: Django's built-in admin at /admin/. Branded dashboard or special
workflow: custom pages behind a staff check. Normal users managing their own things:
regular pages, not admin. Start with the built-in admin.

## Roles
- Superuser: everything. Create with python manage.py createsuperuser. Keep to 1-2 people.
- Staff (is_staff): can enter the admin but only sees what permissions allow.
- Use Groups (for example Moderators) to hold permissions; add users to groups.
- Public sign-ups must never get is_staff or is_superuser.

## Register a model
    @admin.register(Event)
    class EventAdmin(admin.ModelAdmin):
        list_display = ("title", "host", "starts_at", "visibility", "is_cancelled")
        list_filter = ("visibility", "is_cancelled", "starts_at")
        search_fields = ("title", "location", "host__username")
        date_hierarchy = "starts_at"
        list_select_related = ("host",)
        readonly_fields = ("share_token", "created_at")
        actions = ["cancel_events"]

        @admin.action(description="Cancel selected events")
        def cancel_events(self, request, queryset):
            n = queryset.update(is_cancelled=True)
            self.message_user(request, f"{n} event(s) cancelled.")

Adapt field names to the project. Do not put per-row queries in list_display without
annotating the queryset. For CSV export actions, prefix cells that start with =, +, -,
or @ with an apostrophe to prevent spreadsheet formula injection.

## Custom staff page
    @staff_member_required
    def dashboard(request):
        stats = {"events": Event.objects.count(),
                 "cancelled": Event.objects.filter(is_cancelled=True).count()}
        return render(request, "staff/dashboard.html", {"stats": stats})

For a specific permission use @permission_required("app.change_event", raise_exception=True).

## Safe changes and hardening
- Prefer soft delete (is_active or deleted_at) for user-facing data.
- The built-in admin logs changes in LogEntry. Custom pages must log who, what, when.
- If users post content, add a reported flag and a staff review queue.
- No default or shared passwords. Keep DEBUG = False and a proper ALLOWED_HOSTS before deploying.

## Checklist
Log in as a normal user and try staff URLs: they must be blocked. Every staff action
shows a clear message. Every destructive action is confirmed, logged, or reversible.