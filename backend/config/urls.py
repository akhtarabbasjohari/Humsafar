"""Humsafar URL Configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/chat/", include("apps.chat.urls")),
    path("api/itineraries/", include("apps.itineraries.urls")),
]
