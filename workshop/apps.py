"""Configuration de l'application workshop."""

from django.apps import AppConfig


class WorkshopConfig(AppConfig):
    """Configuration de l'application de gestion des ateliers."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "workshop"
