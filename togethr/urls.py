from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("account/", include("members.urls")),
    path("", include("activities.urls")),
    path("manage/", include("adminpanel.urls")),
    path(settings.DJANGO_ADMIN_URL, admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Togethr administration"
admin.site.site_title = "Togethr admin"
admin.site.index_title = "Site administration"
