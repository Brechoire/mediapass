"""Modèles de données pour l'application notifications.

Ce module définit les modèles de données pour la gestion des notifications
et rappels par email.
"""

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class EmailTemplate(models.Model):
    """Modèle pour les templates d'emails de notification.

    Permet de gérer les sujets et contenus des emails depuis l'interface
    d'administration, sans avoir à modifier le code.
    """

    NOTIFICATION_TYPES = [
        ("new_reservation", "Nouvelle réservation"),
        ("reservation_approved", "Réservation approuvée"),
        ("reservation_disapproved", "Réservation désapprouvée"),
        ("structure_validated", "Structure validée"),
        ("poster_request", "Demande d'affiche"),
        ("poster_validated", "Affiche validée"),
        ("poster_rejected", "Affiche rejetée"),
        ("poster_image_uploaded", "Image d'affiche ajoutée"),
        ("reservation_reminder", "Rappel de réservation"),
        ("workshop_reminder", "Rappel d'atelier"),
    ]

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        unique=True,
        verbose_name="Type de notification",
    )
    subject = models.CharField(
        max_length=255,
        verbose_name="Sujet de l'email",
        help_text="Sujet de l'email. Utilisez {{ variable }} pour les données dynamiques.",
    )
    body_html = models.TextField(
        verbose_name="Corps HTML",
        help_text="Template HTML complet. Variables disponibles selon le contexte.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactiver pour ne pas envoyer ce type de notification.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification",
    )

    class Meta:
        verbose_name = "Template d'email"
        verbose_name_plural = "Templates d'emails"
        ordering = ["notification_type"]

    def __str__(self):
        return f"{self.get_notification_type_display()} — {self.subject[:60]}"


class NotificationRecipient(models.Model):
    """Modèle pour les destinataires des notifications par email.

    Permet de gérer dynamiquement les adresses email qui recevront
    les notifications.
    """

    NOTIFICATION_TYPES = EmailTemplate.NOTIFICATION_TYPES

    email = models.EmailField(
        verbose_name="Adresse email",
        help_text="Adresse email du destinataire",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactiver pour ne plus recevoir de notifications",
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default="reservation_reminder",
        verbose_name="Type de notification",
        help_text="Type de notification à recevoir",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
        db_index=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    class Meta:
        verbose_name = "Destinataire de notification"
        verbose_name_plural = "Destinataires de notifications"
        ordering = ["-created_at"]
        unique_together = ["email", "notification_type"]
        indexes = [
            models.Index(fields=["is_active", "notification_type"]),
        ]

    def __str__(self):
        """Retourne l'adresse email du destinataire.

        Returns:
            str: L'adresse email du destinataire.
        """
        status = "Actif" if self.is_active else "Inactif"
        return f"{self.email} ({status})"


class ReservationReminder(models.Model):
    """Modèle pour tracker les rappels de réservation envoyés.

    Permet d'éviter les doublons et de garder un historique
    des rappels envoyés pour chaque réservation.
    """

    reservation = models.ForeignKey(
        "shop.Reservation",
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name="Réservation",
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'envoi",
    )
    recipients = models.TextField(
        verbose_name="Destinataires",
        help_text="Liste des adresses email ayant reçu le rappel",
    )

    class Meta:
        verbose_name = "Rappel de réservation"
        verbose_name_plural = "Rappels de réservations"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["reservation", "sent_at"]),
        ]

    def __str__(self):
        """Retourne une description du rappel.

        Returns:
            str: Une chaîne décrivant le rappel avec la réservation
                et la date d'envoi.
        """
        return (
            f"Rappel pour {self.reservation} "
            f"envoyé le {self.sent_at.strftime('%d/%m/%Y à %H:%M')}"
        )


class WorkshopReminder(models.Model):
    """Modèle pour tracker les rappels d'atelier envoyés."""

    workshop = models.ForeignKey(
        "library_workshops.Workshop",
        on_delete=models.CASCADE,
        related_name="reminders",
        verbose_name="Atelier",
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'envoi",
    )
    recipients = models.TextField(
        verbose_name="Destinataires",
        help_text="Liste des adresses email ayant reçu le rappel",
    )

    class Meta:
        verbose_name = "Rappel d'atelier"
        verbose_name_plural = "Rappels d'ateliers"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["workshop", "sent_at"]),
        ]

    def __str__(self):
        return (
            f"Rappel pour {self.workshop} "
            f"envoyé le {self.sent_at.strftime('%d/%m/%Y à %H:%M')}"
        )


class NotificationSettings(models.Model):
    """Modèle singleton pour les paramètres de notification.

    Permet de configurer l'heure d'envoi des rappels de réservation.
    Une seule instance de ce modèle doit exister dans la base de données.
    """

    reminder_send_hour = models.IntegerField(
        default=9,
        verbose_name="Heure d'envoi",
        help_text="Heure d'envoi des rappels (0-23). Par défaut : 9h00",
        validators=[
            MinValueValidator(0),
            MaxValueValidator(23),
        ],
    )
    reminder_send_minute = models.IntegerField(
        default=0,
        verbose_name="Minute d'envoi",
        help_text="Minute d'envoi des rappels (0-59). Par défaut : 0",
        validators=[
            MinValueValidator(0),
            MaxValueValidator(59),
        ],
    )
    reminders_enabled = models.BooleanField(
        default=True,
        verbose_name="Rappels réservation activés",
        help_text="Active ou désactive l'envoi automatique des rappels de réservation.",
    )
    workshop_reminders_enabled = models.BooleanField(
        default=True,
        verbose_name="Rappels atelier activés",
        help_text="Active ou désactive l'envoi automatique des rappels d'atelier.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    class Meta:
        verbose_name = "Paramètres de notification"
        verbose_name_plural = "Paramètres de notification"
        ordering = ["-updated_at"]

    def __str__(self):
        """Retourne l'heure configurée.

        Returns:
            str: L'heure d'envoi formatée (HH:MM).
        """
        return f"{self.reminder_send_hour:02d}:{self.reminder_send_minute:02d}"

    def get_send_time(self):
        """Retourne l'heure d'envoi formatée.

        Returns:
            str: L'heure d'envoi au format HH:MM.
        """
        return f"{self.reminder_send_hour:02d}:{self.reminder_send_minute:02d}"

    @classmethod
    def get_settings(cls):
        """Récupère ou crée l'instance singleton des paramètres.

        Returns:
            NotificationSettings: L'instance unique des paramètres.
        """
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                "reminder_send_hour": 9,
                "reminder_send_minute": 0,
                "reminders_enabled": True,
            },
        )
        return settings

    def save(self, *args, **kwargs):
        """Sauvegarde en forçant l'ID à 1 pour garantir le singleton."""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Empêche la suppression de l'instance singleton."""
        pass

