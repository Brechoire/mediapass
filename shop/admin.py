"""Configuration de l'interface d'administration pour l'application shop.

Ce module configure l'interface d'administration Django pour les modèles
Product et Reservation, en définissant les champs à afficher, les filtres
et les options de recherche.
"""

from django.contrib import admin

from .models import Product, Reservation


class ProductAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les produits.

    Cette classe définit l'affichage et les fonctionnalités de l'interface
    d'administration pour le modèle Product, notamment les champs à afficher
    dans la liste, les filtres disponibles et les champs de recherche.
    """

    list_display = ("name", "quantity", "category", "price", "status")
    list_filter = ("status", "category")
    search_fields = ("name", "description", "category__name")


class ReservationAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les réservations.

    Cette classe définit l'affichage de l'interface d'administration pour
    le modèle Reservation, notamment les champs à afficher dans la liste
    des réservations.
    """

    list_display = (
        "product",
        "structure",
        "start_date",
        "end_date",
        "quantity",
        "deposit_time",
        "pickup_time",
    )


admin.site.register(Product, ProductAdmin)
admin.site.register(Reservation, ReservationAdmin)
