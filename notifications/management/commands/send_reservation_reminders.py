"""Commande management pour envoyer les rappels de réservation.

Cette commande doit être exécutée quotidiennement via cron pour envoyer
les emails de rappel J-1 pour les réservations commençant demain (arrivée)
et se terminant demain (fin).
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
from notifications.services import (
    send_reservation_arrival_reminder_email,
    send_reservation_reminder_email,
)


class Command(BaseCommand):
    """Commande pour envoyer les rappels de réservation J-1."""

    help = (
        "Envoie les emails de rappel pour les réservations approuvées "
        "qui commencent demain (J-1 arrivée) ou se terminent demain (J-1 fin)."
    )

    def handle(self, *args, **options):
        """Exécute la commande pour envoyer les rappels."""
        settings = NotificationSettings.get_settings()
        if not settings.reminders_enabled:
            self.stdout.write(
                self.style.WARNING(
                    "Les rappels de réservation sont désactivés. "
                    "Activez-les dans les paramètres de notification pour envoyer des rappels."
                )
            )
            return

        # Calculer la date de demain (fuseau local Europe/Paris)
        tomorrow = timezone.localdate() + timedelta(days=1)
        tomorrow_start = timezone.make_aware(
            datetime.combine(tomorrow, datetime.min.time())
        )
        tomorrow_end = timezone.make_aware(
            datetime.combine(tomorrow, datetime.max.time())
        )

        # Récupérer les destinataires actifs une seule fois
        recipients = NotificationRecipient.objects.filter(
            is_active=True,
            notification_type="reservation_reminder",
        ).values_list("email", flat=True)

        recipient_list = list(recipients)
        if not recipient_list:
            self.stdout.write(
                self.style.WARNING(
                    "Aucun destinataire actif trouvé pour les rappels de réservation."
                )
            )
            return

        sent_arrival = self._send_arrival_reminders(
            tomorrow, tomorrow_start, tomorrow_end, recipient_list
        )
        sent_ending = self._send_ending_reminders(
            tomorrow, tomorrow_start, tomorrow_end, recipient_list
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Résumé : {sent_arrival} rappel(s) arrivée envoyé(s), "
                f"{sent_ending} rappel(s) fin envoyé(s)"
            )
        )

    def _send_arrival_reminders(
        self, tomorrow, tomorrow_start, tomorrow_end, recipient_list
    ):
        """Envoie les rappels J-1 arrivée (start_date == demain)."""
        arrivals = (
            Reservation.objects.select_related("product", "structure")
            .filter(
                is_approved=True,
                arrival_reminder_sent=False,
                start_date__gte=tomorrow_start,
                start_date__lte=tomorrow_end,
            )
            .exclude(
                # Réservation d'un seul jour : seul le rappel arrivée part
                # (le rappel fin est ignoré pour éviter le doublon).
                end_date__gte=tomorrow_start,
                end_date__lte=tomorrow_end,
            )
        )

        # Cas particulier : réservations d'un seul jour (start et end demain).
        # Elles ont été exclues ci-dessus pour le rappel fin, on les réintègre
        # ici en rappel arrivée unique.
        single_day = Reservation.objects.select_related(
            "product", "structure"
        ).filter(
            is_approved=True,
            arrival_reminder_sent=False,
            start_date__gte=tomorrow_start,
            start_date__lte=tomorrow_end,
            end_date__gte=tomorrow_start,
            end_date__lte=tomorrow_end,
        )

        # Union sans doublon
        arrival_ids = set(arrivals.values_list("id", flat=True)) | set(
            single_day.values_list("id", flat=True)
        )
        if not arrival_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Aucune arrivée à rappeler pour le {tomorrow.strftime('%d/%m/%Y')}."
                )
            )
            return 0

        arrival_reservations = Reservation.objects.select_related(
            "product", "structure"
        ).filter(id__in=arrival_ids)

        self.stdout.write(
            f"Envoi des rappels ARRIVÉE pour {arrival_reservations.count()} réservation(s) "
            f"à {len(recipient_list)} destinataire(s)..."
        )
        return self._send_batch(
            arrival_reservations, recipient_list, kind="arrival"
        )

    def _send_ending_reminders(
        self, tomorrow, tomorrow_start, tomorrow_end, recipient_list
    ):
        """Envoie les rappels J-1 fin (end_date == demain, hors 1 jour)."""
        endings = (
            Reservation.objects.select_related("product", "structure")
            .filter(
                is_approved=True,
                reminder_sent=False,
                end_date__gte=tomorrow_start,
                end_date__lte=tomorrow_end,
            )
            .exclude(
                # Réservations d'un seul jour déjà couvertes par le rappel arrivée
                start_date__gte=tomorrow_start,
                start_date__lte=tomorrow_end,
            )
        )

        if not endings.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"Aucune fin à rappeler pour le {tomorrow.strftime('%d/%m/%Y')}."
                )
            )
            return 0

        self.stdout.write(
            f"Envoi des rappels FIN pour {endings.count()} réservation(s) "
            f"à {len(recipient_list)} destinataire(s)..."
        )
        return self._send_batch(endings, recipient_list, kind="ending")

    def _send_batch(self, reservations, recipient_list, kind):
        """Envoie un lot de rappels et marque les flags."""
        if kind == "arrival":
            send_fn = send_reservation_arrival_reminder_email
            flag_field = "arrival_reminder_sent"
            label = "ARRIVÉE"
        else:
            send_fn = send_reservation_reminder_email
            flag_field = "reminder_sent"
            label = "FIN"

        sent_count = 0
        for reservation in reservations:
            try:
                success = send_fn(reservation, recipient_list)
                if success:
                    setattr(reservation, flag_field, True)
                    reservation.save(update_fields=[flag_field])
                    ReservationReminder.objects.create(
                        reservation=reservation,
                        recipients=", ".join(recipient_list),
                        kind=kind,
                    )
                    sent_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[OK] Rappel {label} envoye pour la reservation "
                            f"#{reservation.id} ({reservation.product.name} - "
                            f"{reservation.structure.name})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[ERREUR] Echec envoi du rappel {label} pour la "
                            f"reservation #{reservation.id}"
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[ERREUR] Traitement reservation "
                        f"#{reservation.id}: {str(e)}"
                    )
                )
        return sent_count
