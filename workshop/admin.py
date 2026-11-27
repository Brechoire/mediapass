"""Configuration de l'interface d'administration pour les ateliers."""

from django.contrib import admin

from .models import Location, Workshop, WorkshopName
from .naming import resolve_workshop_name


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


@admin.register(WorkshopName)
class WorkshopNameAdmin(admin.ModelAdmin):
    """Configuration de la liste des noms d'ateliers."""

    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name", "normalized")
    readonly_fields = ("normalized", "created_at", "updated_at")
    ordering = ("name",)

    fieldsets = (
        (
            "Nom",
            {
                "fields": ("name",),
                "description": (
                    "Nom proposé dans les formulaires d'atelier. "
                    "La casse, les accents et la ponctuation sont normalisés. "
                    "Renommer une entrée ne modifie pas les ateliers existants : "
                    "utilisez la commande normalize_workshop_names --apply."
                ),
            },
        ),
        (
            "Métadonnées",
            {
                "fields": ("normalized", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


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
    list_filter = (
        "location",
        "date",
        "poster_required",
        "class_welcome",
    )
    search_fields = ("name", "location__name")
    date_hierarchy = "date"
    readonly_fields = (
        "series",
        "series_index",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        (
            "Informations générales",
            {
                "fields": (
                    "name",
                    "location",
                    "description_poster_valide",
                )
            },
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
        (
            "Média",
            {"fields": ("image",), "classes": ("collapse",)},
        ),
        (
            "Suivi",
            {
                "fields": (
                    "series",
                    "series_index",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Canonise le nom et renseigne l'audit utilisateur."""
        if obj.name:
            obj.name = resolve_workshop_name(obj.name).name
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
