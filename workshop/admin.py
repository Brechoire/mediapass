"""Configuration de l'interface d'administration pour les ateliers."""

from django.contrib import admin

from .models import Location, Workshop


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Configuration de l'administration des lieux."""

    list_display = ("name", "city", "zip_code", "address")
    search_fields = ("name", "city")
    list_filter = ("city",)

    fieldsets = (
        ("Informations principales", {"fields": ("name", "address")}),
        ("Localisation", {"fields": ("zip_code", "city")}),
    )

    def get_list_display_links(self, request, list_display):
        """Retourne les champs cliquables dans la liste.

        Args:
            request: La requête HTTP.
            list_display: Liste des champs affichés.

        Returns:
            tuple: Tuple contenant les champs cliquables.
        """
        return ("name",)


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    """Configuration de l'administration des ateliers."""

    list_display = (
        "name",
        "location",
        "date",
        "start_time",
        "end_time",
        "number_registered",
    )
    list_filter = ("location", "date", "poster_required", "class_welcome")
    search_fields = ("name", "location__name")
    date_hierarchy = "date"

    fieldsets = (
        (
            "Informations générales",
            {"fields": ("name", "location", "description_poster_valide")},
        ),
        (
            "Dates et horaires",
            {"fields": (("date", "date_end"), ("start_time", "end_time"))},
        ),
        (
            "Participants",
            {
                "fields": (
                    "number_registered",
                    "number_attendees",
                    "class_welcome",
                )
            },
        ),
        (
            "Communication",
            {
                "fields": (
                    "poster_required",
                    "poster_valide",
                    "instagram",
                    "facebook",
                    "mail",
                    "portail",
                    "vdn",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Média", {"fields": ("image",), "classes": ("collapse",)}),
    )
