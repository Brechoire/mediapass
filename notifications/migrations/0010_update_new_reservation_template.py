"""Redesign du mail "nouvelle demande" : style rappels + lien vers la demande.

Ne remplace le body existant que s'il est encore identique a l'ancien defaut,
pour preserver toute personnalisation faite depuis l'admin.
"""

from django.db import migrations


OLD_BODY_HTML = "<h2>Nouvelle demande de réservation</h2>\n<p><strong>Produit :</strong> {{ product.name }}</p>\n<p><strong>Structure :</strong> {{ reservation.structure.name }}</p>\n<p><strong>Dates :</strong> du {{ reservation.start_date }} au {{ reservation.end_date }}</p>\n<p><strong>Quantité :</strong> {{ reservation.quantity }}</p>\n<p>Connectez-vous à l'interface d'administration pour gérer cette réservation.</p>"


NEW_BODY_HTML = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #ecf0f1;">\n<tr>\n<td align="center" style="padding: 20px 10px;">\n<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; max-width: 600px; width: 100%;">\n<tr>\n<td align="center" bgcolor="#4a6fa5" style="background-color: #4a6fa5; padding: 30px 20px; border-radius: 8px 8px 0 0;">\n<p style="margin: 0 0 10px; font-size: 28px; line-height: 1;">&#128203;</p>\n<h1 style="margin: 0; font-size: 26px; font-weight: bold; color: #ffffff; font-family: Arial, Helvetica, sans-serif;">Nouvelle demande de r&eacute;servation</h1>\n<p style="margin: 8px 0 0; font-size: 16px; color: #ffffff; font-family: Arial, Helvetica, sans-serif;">Une demande est en attente de traitement</p>\n</td>\n</tr>\n<tr>\n<td align="center" style="padding: 30px 30px 10px;">\n<h2 style="margin: 0 0 10px; font-size: 20px; font-weight: bold; color: #2c3e50; font-family: Arial, Helvetica, sans-serif;">{{ product.name }}</h2>\n<p style="margin: 0; font-size: 15px; color: #555555; font-family: Arial, Helvetica, sans-serif;">Demand&eacute;e par {{ reservation.structure.name }}</p>\n</td>\n</tr>\n<tr>\n<td style="padding: 10px 30px 10px;">\n<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #e8eef7; border-radius: 6px;">\n<tr>\n<td style="padding: 20px; border-left: 4px solid #4a6fa5;">\n<h3 style="margin: 0 0 15px; font-size: 17px; font-weight: bold; color: #2c3e50; font-family: Arial, Helvetica, sans-serif;">D&eacute;tails de la demande</h3>\n<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">\n<tr>\n<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">\n<span style="font-size: 12px; color: #6c757d;">PRODUIT</span><br>\n<strong style="font-size: 16px; color: #2c3e50;">{{ product.name }}</strong>\n</td>\n</tr>\n<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>\n<tr>\n<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">\n<span style="font-size: 12px; color: #6c757d;">STRUCTURE</span><br>\n<strong style="font-size: 16px; color: #2c3e50;">{{ reservation.structure.name }}</strong>\n</td>\n</tr>\n<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>\n<tr>\n<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">\n<span style="font-size: 12px; color: #6c757d;">P&Eacute;RIODE</span><br>\n<strong style="font-size: 15px; color: #2c3e50;">Du {{ reservation.start_date|date:"d/m/Y à H:i" }}<br>Au {{ reservation.end_date|date:"d/m/Y à H:i" }}</strong>\n</td>\n</tr>\n<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>\n<tr>\n<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">\n<span style="font-size: 12px; color: #6c757d;">QUANTIT&Eacute;</span><br>\n<strong style="font-size: 16px; color: #2c3e50;">{{ reservation.quantity }}</strong>\n</td>\n</tr>\n{% if reservation.description %}\n<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>\n<tr>\n<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">\n<span style="font-size: 12px; color: #6c757d;">DESCRIPTION</span><br>\n<span style="font-size: 14px; color: #2c3e50;">{{ reservation.description }}</span>\n</td>\n</tr>\n{% endif %}\n</table>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td style="padding: 10px 30px;">\n<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #e8eef7; border-radius: 6px;">\n<tr>\n<td style="padding: 14px; border-left: 4px solid #4a6fa5; font-family: Arial, Helvetica, sans-serif; font-size: 14px; color: #2f4d75;">\n<strong>&#9888;</strong> Cette demande est en attente. Approuvez-la ou d&eacute;sapprouvez-la depuis la file d\'attente.\n</td>\n</tr>\n</table>\n</td>\n</tr>\n<tr>\n<td align="center" style="padding: 25px 30px;">\n<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">\n<tr>\n<td align="center" bgcolor="#4a6fa5" style="background-color: #4a6fa5; border-radius: 6px; padding: 14px 28px;">\n<a href="{{ reservation_url }}" style="font-family: Arial, Helvetica, sans-serif; font-size: 16px; font-weight: bold; color: #ffffff; text-decoration: none; display: inline-block;">&#128065; Voir la demande de r&eacute;servation</a>\n</td>\n</tr>\n</table>\n<p style="margin: 12px 0 0; font-size: 13px; color: #6c757d; font-family: Arial, Helvetica, sans-serif;">Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :<br>{{ reservation_url }}</p>\n</td>\n</tr>\n<tr>\n<td align="center" style="background-color: #f8f9fa; padding: 20px; border-top: 1px solid #e9ecef; border-radius: 0 0 8px 8px; font-family: Arial, Helvetica, sans-serif;">\n<p style="margin: 0 0 10px; font-size: 13px; color: #6c757d;">Ceci est un message automatique, merci de ne pas y r&eacute;pondre.</p>\n<p style="margin: 0; font-size: 12px; color: #6c757d;">&copy; {% now "Y" %} Mediapass - Tous droits r&eacute;serv&eacute;s</p>\n<p style="margin: 5px 0 0; font-size: 11px; color: #adb5bd;">Plateforme de gestion des r&eacute;servations</p>\n</td>\n</tr>\n</table>\n</td>\n</tr>\n</table>'


def apply_new_template(apps, schema_editor):
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    tpl, created = EmailTemplate.objects.get_or_create(
        notification_type="new_reservation",
        defaults={
            "subject": "Nouvelle demande de réservation — {{ product.name }}",
            "body_html": NEW_BODY_HTML,
        },
    )
    if not created and (tpl.body_html or "").strip() == OLD_BODY_HTML.strip():
        tpl.body_html = NEW_BODY_HTML
        tpl.save(update_fields=["body_html"])


def restore_old_template(apps, schema_editor):
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    try:
        tpl = EmailTemplate.objects.get(notification_type="new_reservation")
    except EmailTemplate.DoesNotExist:
        return
    if (tpl.body_html or "").strip() == NEW_BODY_HTML.strip():
        tpl.body_html = OLD_BODY_HTML
        tpl.save(update_fields=["body_html"])


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0009_reservationreminder_kind"),
    ]

    operations = [
        migrations.RunPython(apply_new_template, restore_old_template),
    ]
