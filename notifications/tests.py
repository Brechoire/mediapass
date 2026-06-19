from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

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
