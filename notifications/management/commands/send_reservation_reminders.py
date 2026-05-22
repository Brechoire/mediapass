"""Commande management pour envoyer les rappels de réservation.

Cette commande doit être exécutée quotidiennement via cron pour envoyer
les emails de rappel J-1 pour les réservations se terminant le lendemain.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime

from shop.models import Reservation
from notifications.models import (
    NotificationRecipient,
    NotificationSettings,
    ReservationReminder,
)
from notifications.services import send_reservation_reminder_email


class Command(BaseCommand):
    """Commande pour envoyer les rappels de réservation J-1."""

    help = (
        "Envoie les emails de rappel pour les réservations approuvées "
        "qui se terminent demain (J-1)."
    )

    def handle(self, *args, **options):
        """Exécute la commande pour envoyer les rappels."""
        # Vérifier si les rappels sont activés
        settings = NotificationSettings.get_settings()
        if not settings.reminders_enabled:
            self.stdout.write(
                self.style.WARNING(
                    "Les rappels de réservation sont désactivés. "
                    "Activez-les dans les paramètres de notification pour envoyer des rappels."
                )
            )
            return

        # Calculer la date de demain (fin de journée)
        tomorrow = timezone.now().date() + timedelta(days=1)
        tomorrow_start = timezone.make_aware(
            datetime.combine(tomorrow, datetime.min.time())
        )
        tomorrow_end = timezone.make_aware(
            datetime.combine(tomorrow, datetime.max.time())
        )

        # Récupérer les réservations approuvées qui se terminent demain
        # et pour lesquelles le rappel n'a pas encore été envoyé
        reservations = Reservation.objects.select_related(
            'product', 'structure'
        ).filter(
            is_approved=True,
            reminder_sent=False,
            end_date__gte=tomorrow_start,
            end_date__lte=tomorrow_end,
        )

        if not reservations.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"Aucune réservation à rappeler pour le {tomorrow.strftime('%d/%m/%Y')}."
                )
            )
            return

        # Récupérer les destinataires actifs pour les rappels de réservation
        recipients = NotificationRecipient.objects.filter(
            is_active=True,
            notification_type="reservation_reminder",
        ).values_list("email", flat=True)

        if not recipients:
            self.stdout.write(
                self.style.WARNING(
                    "Aucun destinataire actif trouvé pour les rappels de réservation."
                )
            )
            return

        recipient_list = list(recipients)
        self.stdout.write(
            f"Envoi des rappels pour {reservations.count()} réservation(s) "
            f"à {len(recipient_list)} destinataire(s)..."
        )

        # Envoyer les rappels pour chaque réservation
        sent_count = 0
        error_count = 0

        for reservation in reservations:
            try:
                # Envoyer l'email
                success = send_reservation_reminder_email(
                    reservation, recipient_list
                )

                if success:
                    # Marquer le rappel comme envoyé
                    reservation.reminder_sent = True
                    reservation.save(update_fields=['reminder_sent'])

                    # Créer un enregistrement de rappel pour l'historique
                    ReservationReminder.objects.create(
                        reservation=reservation,
                        recipients=", ".join(recipient_list),
                    )

                    sent_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Rappel envoyé pour la réservation "
                            f"#{reservation.id} ({reservation.product.name} - "
                            f"{reservation.structure.name})"
                        )
                    )
                else:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Erreur lors de l'envoi du rappel pour la "
                            f"réservation #{reservation.id}"
                        )
                    )
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Erreur lors du traitement de la réservation "
                        f"#{reservation.id}: {str(e)}"
                    )
                )

        # Résumé
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Résumé : {sent_count} rappel(s) envoyé(s), "
                f"{error_count} erreur(s)"
            )
        )

