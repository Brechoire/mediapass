"""Commande management pour envoyer les rappels d'atelier.

Cette commande doit être exécutée quotidiennement via cron pour envoyer
les emails de rappel J-1 pour les ateliers ayant lieu le lendemain.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime

from django.db.models import Prefetch
from library_workshops.models import Workshop, WorkshopParticipant
from notifications.models import (
    NotificationRecipient,
    NotificationSettings,
    WorkshopReminder,
)
from notifications.services import send_workshop_reminder_email


class Command(BaseCommand):
    help = "Envoie les rappels J-1 pour les ateliers"

    def handle(self, *args, **options):
        settings = NotificationSettings.get_settings()

        if not settings.workshop_reminders_enabled:
            self.stdout.write(self.style.WARNING(
                "Les rappels d'atelier sont désactivés."
            ))
            return

        tomorrow = timezone.now().date() + timedelta(days=1)
        tomorrow_end = datetime.combine(
            tomorrow, timezone.now().time().max
        ).replace(tzinfo=timezone.now().tzinfo)

        workshops = Workshop.objects.filter(
            start_date=tomorrow,
            reminder_sent=False,
        ).prefetch_related(Prefetch('participants',
            queryset=WorkshopParticipant.objects.filter(status='confirmed')
            .exclude(email__isnull=True).exclude(email__exact=''),
            to_attr='confirmed_participants_list'
        ))

        if not workshops.exists():
            self.stdout.write("Aucun atelier demain.")
            return

        recipients = list(
            NotificationRecipient.objects.filter(
                is_active=True,
                notification_type="workshop_reminder",
            ).values_list("email", flat=True)
        )

        if not recipients:
            self.stdout.write(self.style.WARNING(
                "Aucun destinataire configuré pour les rappels d'atelier."
            ))
            return

        success_count = 0
        skip_count = 0

        for workshop in workshops:
            participants = list(getattr(workshop, 'confirmed_participants_list', []))

            if not participants:
                self.stdout.write(
                    f"  {workshop.title}: aucun participant avec email, ignoré"
                )
                workshop.reminder_sent = True
                workshop.save(update_fields=['reminder_sent'])
                skip_count += 1
                continue

            all_recipients = list(recipients)
            for p in participants:
                if p.email and p.email not in all_recipients:
                    all_recipients.append(p.email)

            success = send_workshop_reminder_email(
                workshop, participants, all_recipients
            )

            if success:
                WorkshopReminder.objects.create(
                    workshop=workshop,
                    recipients=", ".join(all_recipients),
                )
                workshop.reminder_sent = True
                workshop.save(update_fields=['reminder_sent'])
                success_count += 1
                self.stdout.write(f"  ✓ {workshop.title}: rappel envoyé à {len(all_recipients)} destinataires")
            else:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {workshop.title}: échec d'envoi"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nRappels envoyés : {success_count}, ignorés : {skip_count}"
        ))
