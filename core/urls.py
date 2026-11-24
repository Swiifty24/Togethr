from django.conf import settings
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("geo/cities/", views.city_suggestions, name="cities"),
]

if settings.DEBUG:
    urlpatterns += [path("_errors/<int:code>/", views.error_preview, name="error_preview")]
