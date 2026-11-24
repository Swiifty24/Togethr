from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("settings/", views.settings_view, name="settings"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
]
