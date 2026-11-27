"""Séries d'ateliers et champs d'audit."""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "workshop",
            "0008_alter_workshop_image_alter_workshop_number_attendees_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="workshop",
            name="series",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                editable=False,
                help_text="Identifiant commun aux ateliers créés ensemble.",
                null=True,
                verbose_name="Série",
            ),
        ),
        migrations.AddField(
            model_name="workshop",
            name="series_index",
            field=models.PositiveSmallIntegerField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="Position dans la série",
            ),
        ),
        migrations.AddField(
            model_name="workshop",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="Créé le",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="workshop",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
                verbose_name="Modifié le",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="workshop",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Créé par",
            ),
        ),
        migrations.AddField(
            model_name="workshop",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Modifié par",
            ),
        ),
    ]
