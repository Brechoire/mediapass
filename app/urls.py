"""Configuration des URLs principales de l'application.

Ce module définit les points d'entrée URL principaux de l'application,
y compris l'administration et les différentes applications.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

urlpatterns = [
    path("mediapassadmin/", admin.site.urls),
    path("", include("home.urls")),
    path("", include("accounts.urls")),
    path("", include("shop.urls")),
    path("", include("workshop.urls")),
    path("analytics/", include("analytics.urls")),  # Nouvelle URL
    path("kakemono/", include("kakemono.urls")),
    path("mediatheque/ateliers/", include("library_workshops.urls")),
    path("mediatheque/visiteurs/", include("visitor_tracking.urls")),
    path("distribution/", include("distribution.urls")),
    path("notifications/admin/", include("notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path("test404/", lambda request: render(request, "404.html")),
    ]

# Sert les fichiers media/static en développement
# En production, configurer Apache/Nginx pour les servir
urlpatterns += static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)
urlpatterns += static(
    settings.STATIC_URL, document_root=settings.STATIC_ROOT
)
