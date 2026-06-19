"""Ajoute q.simon@cc-sudavesnois.fr et j.brechoire@cc-sudavesnois.fr
comme destinataires des notifications de nouvelle reservation."""

from django.db import migrations

RECIPIENTS = (
    "q.simon@cc-sudavesnois.fr",
    "j.brechoire@cc-sudavesnois.fr",
)


def add_recipients(apps, schema_editor):
    NotificationRecipient = apps.get_model("notifications", "NotificationRecipient")
    for email in RECIPIENTS:
        NotificationRecipient.objects.get_or_create(
            email=email,
            notification_type="new_reservation",
            defaults={"is_active": True},
        )


def remove_recipients(apps, schema_editor):
    NotificationRecipient = apps.get_model("notifications", "NotificationRecipient")
    NotificationRecipient.objects.filter(
        email__in=RECIPIENTS,
        notification_type="new_reservation",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "notifications",
            "0006_emailtemplate_alter_notificationrecipient_email_and_more",
        ),
    ]
    operations = [
        migrations.RunPython(add_recipients, remove_recipients),
    ]
