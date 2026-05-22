"""Configuration de l'interface d'administration pour l'application notifications.

Ce module configure l'interface d'administration Django pour les modèles
NotificationRecipient et ReservationReminder.
"""

from django.contrib import admin

from .models import EmailTemplate, NotificationRecipient, ReservationReminder, WorkshopReminder, NotificationSettings


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les destinataires.

    Cette classe définit l'affichage et les fonctionnalités de l'interface
    d'administration pour le modèle NotificationRecipient.
    """

    list_display = (
        "email",
        "notification_type",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active", "notification_type", "created_at")
    search_fields = ("email",)
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("is_active",)

    fieldsets = (
        (
            "Informations principales",
            {
                "fields": ("email", "notification_type", "is_active"),
            },
        ),
        (
            "Dates",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ReservationReminder)
class ReservationReminderAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les rappels.

    Cette classe définit l'affichage de l'interface d'administration pour
    le modèle ReservationReminder (lecture seule pour l'historique).
    """

    list_display = (
        "reservation",
        "sent_at",
        "recipients",
    )
    list_filter = ("sent_at",)
    search_fields = (
        "reservation__product__name",
        "reservation__structure__name",
        "recipients",
    )
    readonly_fields = (
        "reservation",
        "sent_at",
        "recipients",
    )
    date_hierarchy = "sent_at"

    def has_add_permission(self, request):
        """Désactive la création manuelle de rappels."""
        return False

    def has_change_permission(self, request, obj=None):
        """Désactive la modification des rappels."""
        return False


@admin.register(WorkshopReminder)
class WorkshopReminderAdmin(admin.ModelAdmin):
    list_display = ("workshop", "sent_at", "recipients")
    list_filter = ("sent_at",)
    search_fields = ("workshop__title", "recipients")
    readonly_fields = ("workshop", "sent_at", "recipients")
    date_hierarchy = "sent_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les templates d'emails."""

    list_display = ("notification_type", "subject", "is_active", "updated_at")
    list_filter = ("is_active", "notification_type")
    search_fields = ("subject",)
    list_editable = ("is_active",)
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "Type de notification",
            {"fields": ("notification_type", "is_active")},
        ),
        (
            "Contenu de l'email",
            {
                "fields": ("subject", "body_html"),
                "description": (
                    "Utilisez les variables {{ variable_name }} pour insérer des données dynamiques."
                ),
            },
        ),
        (
            "Informations",
            {"fields": ("updated_at",), "classes": ("collapse",)},
        ),
    )


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    """Configuration de l'interface d'administration pour les paramètres.

    Cette classe définit l'affichage de l'interface d'administration pour
    le modèle NotificationSettings (singleton).
    """

    def has_add_permission(self, request):
        """Empêche l'ajout si une instance existe déjà."""
        return NotificationSettings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        """Empêche la suppression de l'instance singleton."""
        return False

    def get_queryset(self, request):
        """Retourne l'instance singleton ou la crée si elle n'existe pas."""
        qs = super().get_queryset(request)
        if qs.count() == 0:
            NotificationSettings.get_settings()
        return qs

    def save_model(self, request, obj, form, change):
        """Sauvegarde en forçant l'ID à 1 pour garantir le singleton."""
        obj.pk = 1
        super().save_model(request, obj, form, change)

    def get_object(self, request, object_id=None, from_field=None):
        """Récupère ou crée l'instance singleton."""
        if object_id is None:
            object_id = 1
        try:
            return super().get_object(request, object_id, from_field)
        except self.model.DoesNotExist:
            return NotificationSettings.get_settings()

    list_display = (
        "reminders_enabled",
        "workshop_reminders_enabled",
        "reminder_send_hour",
        "reminder_send_minute",
        "get_send_time_display",
        "updated_at",
    )
    list_display_links = ("reminder_send_hour",)
    list_editable = ("reminders_enabled", "workshop_reminders_enabled")
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "Rappels de réservation",
            {
                "fields": ("reminders_enabled",),
                "description": (
                    "Activez ou désactivez l'envoi automatique des rappels de réservation."
                ),
            },
        ),
        (
            "Rappels d'atelier",
            {
                "fields": ("workshop_reminders_enabled",),
                "description": (
                    "Activez ou désactivez l'envoi automatique des rappels J-1 pour les ateliers."
                ),
            },
        ),
        (
            "Configuration de l'heure d'envoi",
            {
                "fields": (
                    "reminder_send_hour",
                    "reminder_send_minute",
                ),
                "description": (
                    "Configurez l'heure à laquelle les rappels de réservation "
                    "seront envoyés chaque jour. Assurez-vous que votre tâche "
                    "cron est configurée pour s'exécuter à cette même heure."
                ),
            },
        ),
        (
            "Informations",
            {
                "fields": ("updated_at",),
                "classes": ("collapse",),
            },
        ),
    )

    def get_send_time_display(self, obj):
        """Affiche l'heure formatée."""
        return obj.get_send_time()

    get_send_time_display.short_description = "Heure d'envoi configurée"

