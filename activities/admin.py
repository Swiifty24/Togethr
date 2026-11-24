from django.contrib import admin

from .models import Activity, Category, Participation


class ParticipationInline(admin.TabularInline):
    model = Participation
    extra = 0
    raw_id_fields = ("user", "invited_by")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "organizer", "category", "date", "status", "visibility")
    list_filter = ("status", "visibility", "category")
    search_fields = ("title", "location", "organizer__username")
    raw_id_fields = ("organizer",)
    inlines = [ParticipationInline]
