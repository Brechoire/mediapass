"""Configuration de l'application accounts.

Ce module contient la configuration principale de l'application accounts.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration de l'application accounts.

    Cette classe définit les paramètres de base de l'application accounts,
    y compris le champ automatique par défaut et le nom de l'application.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
