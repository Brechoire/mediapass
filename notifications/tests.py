from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from shop.models import Category, Product, Reservation, Structure

from .email_service import _absolute_url, create_default_templates, send_notification
from .models import EmailTemplate, NotificationRecipient, NotificationSettings


class EmailTemplateModelTests(TestCase):
    def setUp(self):
        EmailTemplate.objects.filter(notification_type="new_reservation").delete()
        self.template = EmailTemplate.objects.create(
            notification_type="new_reservation",
            subject="Nouvelle r\u00e9servation: {{ product.name }}",
            body_html="<p>R\u00e9servation de {{ product.name }}</p>",
        )

    def test_template_creation(self):
        self.assertEqual(self.template.notification_type, "new_reservation")
        self.assertTrue(self.template.is_active)
        self.assertIn("{{ product.name }}", self.template.subject)

    def test_notification_types_exist(self):
        types = [t[0] for t in EmailTemplate.NOTIFICATION_TYPES]
        expected = [
            "new_reservation",
            "reservation_approved",
            "reservation_disapproved",
            "structure_validated",
            "poster_request",
            "poster_validated",
            "poster_rejected",
            "poster_image_uploaded",
            "reservation_reminder",
            "workshop_reminder",
        ]
        for t in expected:
            self.assertIn(t, types)

    def test_notification_type_unique(self):
        with self.assertRaises(Exception):
            EmailTemplate.objects.create(
                notification_type="new_reservation",
                subject="Doublon",
                body_html="<p>Test</p>",
            )


class NotificationRecipientModelTests(TestCase):
    def setUp(self):
        self.recipient = NotificationRecipient.objects.create(
            email="test@example.com",
            notification_type="new_reservation",
        )

    def test_recipient_creation(self):
        self.assertEqual(self.recipient.email, "test@example.com")
        self.assertTrue(self.recipient.is_active)

    def test_recipient_unique_together(self):
        with self.assertRaises(Exception):
            NotificationRecipient.objects.create(
                email="test@example.com",
                notification_type="new_reservation",
            )


class NotificationSettingsModelTests(TestCase):
    def test_singleton_force_pk(self):
        settings = NotificationSettings.get_settings()
        self.assertEqual(settings.pk, 1)

    def test_get_send_time(self):
        settings = NotificationSettings.get_settings()
        send_time = settings.get_send_time()
        expected = (
            f"{settings.reminder_send_hour:02d}:{settings.reminder_send_minute:02d}"
        )
        self.assertEqual(send_time, expected)

    def test_delete_is_noop(self):
        settings = NotificationSettings.get_settings()
        settings.delete()
        self.assertTrue(NotificationSettings.objects.filter(pk=1).exists())

    def test_save_always_pk1(self):
        settings = NotificationSettings(pk=2, reminders_enabled=False)
        settings.save()
        self.assertEqual(settings.pk, 1)


class NotificationAdminViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", password="admin123", email="admin@test.com"
        )

    def test_email_admin_requires_superuser(self):
        response = self.client.get(reverse("notifications:email_admin"))
        self.assertNotEqual(response.status_code, 200)

    def test_email_admin_superuser(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("notifications:email_admin"))
        self.assertEqual(response.status_code, 200)

    def test_recipient_add_superuser(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("notifications:recipient_add"))
        self.assertEqual(response.status_code, 200)


class NewReservationRecipientsMigrationTests(TestCase):
    """Verifie que les destinataires prevus par la migration 0007 existent
    et sont strictement limites au type new_reservation."""

    MIGRATION_RECIPIENTS = (
        "q.simon@cc-sudavesnois.fr",
        "j.brechoire@cc-sudavesnois.fr",
    )

    def test_recipients_for_new_reservation_exist(self):
        for email in self.MIGRATION_RECIPIENTS:
            self.assertTrue(
                NotificationRecipient.objects.filter(
                    email=email,
                    notification_type="new_reservation",
                    is_active=True,
                ).exists(),
                f"Destinataire manquant: {email}",
            )

    def test_recipients_do_not_receive_other_types(self):
        types = set(
            NotificationRecipient.objects.filter(
                email__in=self.MIGRATION_RECIPIENTS
            ).values_list("notification_type", flat=True)
        )
        self.assertEqual(types, {"new_reservation"})


class DefaultEmailTemplatesMigrationTests(TestCase):
    """Verifie que la migration 0008 a cree tous les templates par defaut."""

    EXPECTED_TYPES = {
        "new_reservation",
        "reservation_approved",
        "reservation_disapproved",
        "structure_validated",
        "poster_request",
        "poster_validated",
        "poster_rejected",
        "poster_image_uploaded",
        "reservation_reminder",
        "workshop_reminder",
    }

    def test_all_default_templates_exist(self):
        existing = set(
            EmailTemplate.objects.filter(is_active=True).values_list(
                "notification_type", flat=True
            )
        )
        missing = self.EXPECTED_TYPES - existing
        self.assertEqual(missing, set(), f"Templates manquants : {missing}")

    def test_new_reservation_template_is_active(self):
        tpl = EmailTemplate.objects.get(notification_type="new_reservation")
        self.assertTrue(tpl.is_active)
        self.assertIn("{{ product.name }}", tpl.subject)


@override_settings(SITE_URL="https://www.mediapass.ccsudavesnois.fr")
class NewReservationEmailTests(TestCase):
    """Le mail de demande contient un lien absolu vers la réservation."""

    def setUp(self):
        EmailTemplate.objects.filter(notification_type="new_reservation").delete()
        NotificationRecipient.objects.filter(
            notification_type="new_reservation"
        ).delete()
        create_default_templates()
        NotificationRecipient.objects.create(
            email="admin@example.com",
            notification_type="new_reservation",
        )
        category = Category.objects.create(name="Cat Mail")
        self.product = Product.objects.create(
            name="Produit Mail",
            quantity=10,
            description="x",
            category=category,
            price=10,
            status=True,
        )
        self.structure = Structure.objects.create(
            name="Structure Mail",
            address="1 rue",
            city="Ville",
            email="s@t.fr",
            zip_code="59000",
            country="FR",
        )
        now = timezone.now()
        self.reservation = Reservation.objects.create(
            product=self.product,
            start_date=now + timezone.timedelta(days=1),
            end_date=now + timezone.timedelta(days=2),
            structure=self.structure,
            quantity=2,
        )

    def _send(self, **context):
        base = {"product": self.product, "reservation": self.reservation}
        base.update(context)
        self.assertTrue(send_notification("new_reservation", base))
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0]

    def test_link_to_reservation_details(self):
        email = self._send()
        expected = (
            "https://www.mediapass.ccsudavesnois.fr"
            + reverse("reservation_details", args=[self.reservation.pk])
        )
        html = email.alternatives[0][0]
        self.assertIn('href="%s"' % expected, html)
        # Lien recopié en clair pour les clients qui bloquent les boutons.
        self.assertIn(expected, html.replace('href="%s"' % expected, ""))
        self.assertIn(expected, email.body)

    def test_reminder_style_layout(self):
        email = self._send()
        html = email.alternatives[0][0]
        self.assertIn("#4a6fa5", html)
        self.assertIn("D&eacute;tails de la demande", html)
        self.assertIn("Structure Mail", html)

    def test_explicit_reservation_url_is_kept(self):
        email = self._send(reservation_url="https://example.com/r/1/")
        html = email.alternatives[0][0]
        self.assertIn("https://example.com/r/1/", html)

    def test_absolute_url_falls_back_to_allowed_host(self):
        with override_settings(
            SITE_URL="http://127.0.0.1:8000",
            ALLOWED_HOSTS=["www.mediapass.ccsudavesnois.fr", "localhost"],
        ):
            self.assertEqual(
                _absolute_url("/reservations/140/"),
                "https://www.mediapass.ccsudavesnois.fr/reservations/140/",
            )
