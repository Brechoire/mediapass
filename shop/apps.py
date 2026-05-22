"""Configuration de l'application shop.

Ce module définit la configuration de l'application shop, notamment
le champ de clé primaire automatique et le nom de l'application.
"""

from django.apps import AppConfig


class ShopConfig(AppConfig):
    """Configuration de l'application shop.

    Cette classe définit les paramètres de base de l'application shop,
    notamment le type de champ automatique pour les clés primaires
    et le nom de l'application.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"
