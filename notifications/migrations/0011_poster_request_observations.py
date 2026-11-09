"""Ajoute les observations de l'atelier au mail « Demande d'affiche ».

Ne remplace le body existant que s'il est encore identique à l'ancien
défaut, pour préserver toute personnalisation faite depuis l'admin.
"""

from django.db import migrations


OLD_BODY_HTML = """<h2>Demande d'affiche pour un atelier</h2>
<p><strong>Atelier :</strong> {{ workshop.name }}</p>
<p><strong>Date :</strong> {{ workshop.date }}</p>
<p><strong>Lieu :</strong> {{ workshop.location.name }}</p>
<p><strong>Horaire :</strong> {{ workshop.start_time }} — {{ workshop.end_time }}</p>
<p>Une affiche est requise pour cet atelier. Merci de la préparer.</p>"""

NEW_BODY_HTML = """<h2>Demande d'affiche pour un atelier</h2>
<p><strong>Atelier :</strong> {{ workshop.name }}</p>
<p><strong>Date :</strong> {{ workshop.date }}</p>
<p><strong>Lieu :</strong> {{ workshop.location.name }}</p>
<p><strong>Horaire :</strong> {{ workshop.start_time }} — {{ workshop.end_time }}</p>
{% if workshop.observations %}<p><strong>Observations :</strong><br>{{ workshop.observations|linebreaksbr }}</p>{% endif %}
<p>Une affiche est requise pour cet atelier. Merci de la préparer.</p>"""


def apply_observations_block(apps, schema_editor):
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    tpl, created = EmailTemplate.objects.get_or_create(
        notification_type="poster_request",
        defaults={
            "subject": "Demande d'affiche — {{ workshop.name }}",
            "body_html": NEW_BODY_HTML,
        },
    )
    if not created and (tpl.body_html or "").strip() == OLD_BODY_HTML.strip():
        tpl.body_html = NEW_BODY_HTML
        tpl.save(update_fields=["body_html"])


def restore_old_template(apps, schema_editor):
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    try:
        tpl = EmailTemplate.objects.get(notification_type="poster_request")
    except EmailTemplate.DoesNotExist:
        return
    if (tpl.body_html or "").strip() == NEW_BODY_HTML.strip():
        tpl.body_html = OLD_BODY_HTML
        tpl.save(update_fields=["body_html"])


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0010_update_new_reservation_template"),
    ]

    operations = [
        migrations.RunPython(apply_observations_block, restore_old_template),
    ]
