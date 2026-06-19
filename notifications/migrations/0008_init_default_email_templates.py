"""Initialise les templates d'email par defaut s'ils n'existent pas."""

from django.db import migrations


def init_templates(apps, schema_editor):
    from notifications.email_service import create_default_templates

    create_default_templates()


def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    EmailTemplate.objects.filter(
        notification_type__in=[
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
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0007_add_new_reservation_recipients"),
    ]
    operations = [
        migrations.RunPython(init_templates, remove_templates),
    ]
