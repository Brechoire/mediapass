"""Configuration de l'application notifications.

Ce module définit la configuration de l'application notifications,
notamment le champ de clé primaire automatique et le nom de l'application.
"""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuration de l'application notifications.

    Cette classe définit les paramètres de base de l'application notifications,
    notamment le type de champ automatique pour les clés primaires
    et le nom de l'application.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Notifications"





