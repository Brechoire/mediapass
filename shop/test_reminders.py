"""Tests des rappels J-1 arrivée et fin pour les réservations shop."""

from datetime import datetime, timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from notifications.models import NotificationRecipient, ReservationReminder
from shop.models import Category, Product, Reservation, Structure


class ReservationReminderCommandTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Cat Rappel")
        self.product = Product.objects.create(
            name="Produit Rappel",
            quantity=10,
            category=category,
            price=10,
            status=True,
        )
        self.structure = Structure.objects.create(
            name="Structure Rappel",
            address="1 rue",
            city="Ville",
            email="structure@test.fr",
            zip_code="00000",
            country="FR",
            valid=True,
            is_registered=True,
        )
        NotificationRecipient.objects.create(
            email="admin@test.fr",
            notification_type="reservation_reminder",
            is_active=True,
        )
        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def _at(self, day, hour=10):
        return timezone.make_aware(
            datetime.combine(day, datetime.min.time()).replace(hour=hour)
        )

    def _create(self, start, end, approved=True):
        return Reservation.objects.create(
            product=self.product,
            structure=self.structure,
            start_date=start,
            end_date=end,
            quantity=1,
            is_approved=approved,
        )

    def test_arrival_reminder_sent_for_start_tomorrow(self):
        """start=demain, end plus tard -> 1 email arrivée le J-1."""
        r = self._create(
            self._at(self.tomorrow),
            self._at(self.tomorrow + timedelta(days=7)),
        )
        call_command("send_reservation_reminders")
        r.refresh_from_db()
        self.assertTrue(r.arrival_reminder_sent)
        self.assertFalse(r.reminder_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("commence demain", mail.outbox[0].subject)
        self.assertTrue(
            ReservationReminder.objects.filter(
                reservation=r, kind="arrival"
            ).exists()
        )

    def test_ending_reminder_sent_for_end_tomorrow(self):
        """end=demain, start avant -> 1 email fin, pas d'email arrivée."""
        r = self._create(
            self._at(self.tomorrow - timedelta(days=5)),
            self._at(self.tomorrow, hour=15),
        )
        call_command("send_reservation_reminders")
        r.refresh_from_db()
        self.assertTrue(r.reminder_sent)
        self.assertFalse(r.arrival_reminder_sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("se terminant demain", mail.outbox[0].subject)
        self.assertTrue(
            ReservationReminder.objects.filter(
                reservation=r, kind="ending"
            ).exists()
        )

    def test_single_day_sends_only_arrival(self):
        """start == end == demain -> un seul email arrivée, pas de doublon."""
        r = self._create(
            self._at(self.tomorrow),
            self._at(self.tomorrow, hour=16),
        )
        call_command("send_reservation_reminders")
        r.refresh_from_db()
        self.assertTrue(r.arrival_reminder_sent)
        self.assertFalse(r.reminder_sent)
        self.assertEqual(len(mail.outbox), 1)
        kinds = list(
            ReservationReminder.objects.filter(reservation=r).values_list(
                "kind", flat=True
            )
        )
        self.assertEqual(kinds, ["arrival"])

    def test_no_reminder_for_pending(self):
        r = self._create(
            self._at(self.tomorrow),
            self._at(self.tomorrow + timedelta(days=2)),
            approved=False,
        )
        call_command("send_reservation_reminders")
        r.refresh_from_db()
        self.assertFalse(r.arrival_reminder_sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_duplicate_on_rerun(self):
        r = self._create(
            self._at(self.tomorrow),
            self._at(self.tomorrow + timedelta(days=2)),
        )
        call_command("send_reservation_reminders")
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox = []
        call_command("send_reservation_reminders")
        self.assertEqual(len(mail.outbox), 0)
        r.refresh_from_db()
        self.assertTrue(r.arrival_reminder_sent)
