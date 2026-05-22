"""Module de configuration de l'application Analytics."""

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """Configuration de l'application Analytics.

    Cette classe définit les paramètres de base de l'application Analytics.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics"
