from django.urls import path

from . import views

app_name = "activities"

urlpatterns = [
    path("home/", views.home, name="home"),
    path("activities/", views.my_activities, name="my_activities"),
    path("activities/new/", views.create, name="create"),
    path("activities/<int:pk>/", views.detail, name="detail"),
    path("activities/<int:pk>/edit/", views.edit, name="edit"),
    path("activities/<int:pk>/cancel/", views.cancel, name="cancel"),
    path("activities/<int:pk>/join/", views.join, name="join"),
    path("activities/<int:pk>/leave/", views.leave, name="leave"),
    path("activities/<int:pk>/respond/", views.respond, name="respond"),
    path("activities/<int:pk>/participants/", views.participants, name="participants"),
    path("activities/<int:pk>/invite/", views.invite, name="invite"),
    path("activities/<int:pk>/participants/<int:participation_pk>/remove/", views.remove_participant, name="remove_participant"),
    path("invitations/", views.invitations, name="invitations"),
    path("calendar/", views.calendar_view, name="calendar"),
]
