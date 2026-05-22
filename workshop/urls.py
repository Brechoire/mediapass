"""Configuration des URLs pour l'application workshop.

Ce module définit les routes URL pour l'application workshop, permettant
d'accéder aux différentes fonctionnalités de gestion des ateliers,
des lieux et des affiches.
"""

from django.urls import path

from . import views

# Note: pas de app_name car les URLs sont incluses à la racine sans préfixe.

urlpatterns = [
    # Gestion des ateliers
    path("ateliers/", views.workshop_list, name="workshop_list"),
    path("atelier/ajout/", views.workshop_create, name="workshop_create"),
    path(
        "atelier/<int:pk>/detail/",
        views.workshop_detail,
        name="workshop_detail",
    ),
    path(
        "atelier/<int:pk>/update/",
        views.workshop_update,
        name="workshop_update",
    ),
    path(
        "atelier/<int:pk>/delete/",
        views.workshop_delete,
        name="workshop_delete",
    ),
    path(
        "atelier/<int:pk>/delete/image",
        views.workshop_delete_image,
        name="workshop_delete_image",
    ),
    path("atelier-du-mois/", views.workshop_month, name="workshop_month"),
    path(
        "atelier/ajout/affiche/<int:pk>",
        views.workshop_valide_poster,
        name="workshop_valide_poster",
    ),
    path(
        "atelier-demande-affiche",
        views.workshops_with_poster,
        name="workshops_with_poster",
    ),
    path("atelier-stats", views.workshop_stats, name="workshop_stats"),
    # Gestion des lieux
    path("lieu/list/", views.location_list, name="location_list"),
    path("lieu/create/", views.location_create, name="location_create"),
    path(
        "lieu/detail/<int:pk>/", views.location_detail, name="location_detail"
    ),
    path(
        "lieu/update/<int:pk>/", views.location_update, name="location_update"
    ),
    path(
        "lieu/delete/<int:pk>/", views.location_delete, name="location_delete"
    ),
    # Gestion des affiches
    path(
        "validation-affiche",
        views.workshop_list_validate_poster_admin,
        name="workshop_validate_poster_admin",
    ),
    path(
        "validation-affiche/<int:pk>",
        views.approve_poster_valide,
        name="approve_poster_valide",
    ),
    path(
        "export/workshops/csv/",
        views.export_workshops_csv,
        name="export_workshops_csv",
    ),
]
