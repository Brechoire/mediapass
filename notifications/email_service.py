"""Service centralisé pour l'envoi d'emails de notification.

Ce module remplace tous les appels directs à send_mail() et EmailMultiAlternatives()
dispersés dans les vues. Les destinataires et templates sont gérés depuis l'admin.
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils import timezone

from .models import EmailTemplate, NotificationRecipient

logger = logging.getLogger(__name__)


def _absolute_url(path):
    """Construit une URL absolue vers la plateforme.

    Utilise SITE_URL s'il désigne un hôte réel, sinon le premier hôte
    non local de ALLOWED_HOSTS (ex. www.mediapass.ccsudavesnois.fr).
    """
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if not base or "127.0.0.1" in base or "localhost" in base:
        hosts = [
            h
            for h in settings.ALLOWED_HOSTS
            if h not in ("localhost", "127.0.0.1", "[::1]", "testserver")
        ]
        base = "https://" + (hosts[0] if hosts else "localhost")
    return base + path


def get_recipients(notification_type):
    """Récupère les destinataires actifs pour un type de notification."""
    return list(
        NotificationRecipient.objects.filter(
            is_active=True,
            notification_type=notification_type,
        ).values_list("email", flat=True)
    )


def send_notification(notification_type, context, extra_recipients=None):
    """Envoie un email selon le type de notification.

    Args:
        notification_type: Clé du type de notification (ex: "new_reservation")
        context: Dictionnaire de variables pour le template
        extra_recipients: Liste d'emails supplémentaires (ex: structure.email)

    Returns:
        bool: True si l'email a été envoyé avec succès
    """
    try:
        template = EmailTemplate.objects.get(
            notification_type=notification_type, is_active=True
        )
    except EmailTemplate.DoesNotExist:
        logger.warning("Template introuvable ou inactif : %s", notification_type)
        return False

    recipients = get_recipients(notification_type)
    if extra_recipients:
        for r in extra_recipients:
            if r and r not in recipients:
                recipients.append(r)

    if not recipients:
        logger.info("Aucun destinataire pour : %s", notification_type)
        return False

    context.setdefault("site_url", settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost")
    if "reservation_url" not in context:
        reservation = context.get("reservation")
        if reservation is not None and getattr(reservation, "pk", None):
            context["reservation_url"] = _absolute_url(
                reverse("reservation_details", args=[reservation.pk])
            )

    subject = _render_template_string(template.subject, context)
    html_content = _render_template_string(template.body_html, context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, recipients
    )
    email.attach_alternative(html_content, "text/html")

    try:
        email.send()
        logger.info("Email %s envoyé à %s", notification_type, ", ".join(recipients))
        return True
    except Exception as e:
        logger.error("Erreur envoi %s : %s", notification_type, str(e))
        return False


def _render_template_string(template_str, context):
    """Rend une chaîne Django template simple avec le contexte donné."""
    from django.template import engines
    django_engine = engines["django"]
    template = django_engine.from_string(template_str)
    return template.render(context)


def create_default_templates():
    """Crée les templates par défaut si absents."""
    defaults = {
        "new_reservation": {
            "subject": "Nouvelle demande de réservation — {{ product.name }}",
            "body_html": """<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #ecf0f1;">
<tr>
<td align="center" style="padding: 20px 10px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; max-width: 600px; width: 100%;">
<tr>
<td align="center" bgcolor="#4a6fa5" style="background-color: #4a6fa5; padding: 30px 20px; border-radius: 8px 8px 0 0;">
<p style="margin: 0 0 10px; font-size: 28px; line-height: 1;">&#128203;</p>
<h1 style="margin: 0; font-size: 26px; font-weight: bold; color: #ffffff; font-family: Arial, Helvetica, sans-serif;">Nouvelle demande de r&eacute;servation</h1>
<p style="margin: 8px 0 0; font-size: 16px; color: #ffffff; font-family: Arial, Helvetica, sans-serif;">Une demande est en attente de traitement</p>
</td>
</tr>
<tr>
<td align="center" style="padding: 30px 30px 10px;">
<h2 style="margin: 0 0 10px; font-size: 20px; font-weight: bold; color: #2c3e50; font-family: Arial, Helvetica, sans-serif;">{{ product.name }}</h2>
<p style="margin: 0; font-size: 15px; color: #555555; font-family: Arial, Helvetica, sans-serif;">Demand&eacute;e par {{ reservation.structure.name }}</p>
</td>
</tr>
<tr>
<td style="padding: 10px 30px 10px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #e8eef7; border-radius: 6px;">
<tr>
<td style="padding: 20px; border-left: 4px solid #4a6fa5;">
<h3 style="margin: 0 0 15px; font-size: 17px; font-weight: bold; color: #2c3e50; font-family: Arial, Helvetica, sans-serif;">D&eacute;tails de la demande</h3>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">
<span style="font-size: 12px; color: #6c757d;">PRODUIT</span><br>
<strong style="font-size: 16px; color: #2c3e50;">{{ product.name }}</strong>
</td>
</tr>
<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>
<tr>
<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">
<span style="font-size: 12px; color: #6c757d;">STRUCTURE</span><br>
<strong style="font-size: 16px; color: #2c3e50;">{{ reservation.structure.name }}</strong>
</td>
</tr>
<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>
<tr>
<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">
<span style="font-size: 12px; color: #6c757d;">P&Eacute;RIODE</span><br>
<strong style="font-size: 15px; color: #2c3e50;">Du {{ reservation.start_date|date:"d/m/Y à H:i" }}<br>Au {{ reservation.end_date|date:"d/m/Y à H:i" }}</strong>
</td>
</tr>
<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>
<tr>
<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">
<span style="font-size: 12px; color: #6c757d;">QUANTIT&Eacute;</span><br>
<strong style="font-size: 16px; color: #2c3e50;">{{ reservation.quantity }}</strong>
</td>
</tr>
{% if reservation.description %}
<tr><td style="height: 8px; line-height: 8px;">&nbsp;</td></tr>
<tr>
<td style="padding: 8px 10px; background-color: #ffffff; border-radius: 4px; font-family: Arial, Helvetica, sans-serif;">
<span style="font-size: 12px; color: #6c757d;">DESCRIPTION</span><br>
<span style="font-size: 14px; color: #2c3e50;">{{ reservation.description }}</span>
</td>
</tr>
{% endif %}
</table>
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td style="padding: 10px 30px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #e8eef7; border-radius: 6px;">
<tr>
<td style="padding: 14px; border-left: 4px solid #4a6fa5; font-family: Arial, Helvetica, sans-serif; font-size: 14px; color: #2f4d75;">
<strong>&#9888;</strong> Cette demande est en attente. Approuvez-la ou d&eacute;sapprouvez-la depuis la file d'attente.
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td align="center" style="padding: 25px 30px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
<tr>
<td align="center" bgcolor="#4a6fa5" style="background-color: #4a6fa5; border-radius: 6px; padding: 14px 28px;">
<a href="{{ reservation_url }}" style="font-family: Arial, Helvetica, sans-serif; font-size: 16px; font-weight: bold; color: #ffffff; text-decoration: none; display: inline-block;">&#128065; Voir la demande de r&eacute;servation</a>
</td>
</tr>
</table>
<p style="margin: 12px 0 0; font-size: 13px; color: #6c757d; font-family: Arial, Helvetica, sans-serif;">Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :<br>{{ reservation_url }}</p>
</td>
</tr>
<tr>
<td align="center" style="background-color: #f8f9fa; padding: 20px; border-top: 1px solid #e9ecef; border-radius: 0 0 8px 8px; font-family: Arial, Helvetica, sans-serif;">
<p style="margin: 0 0 10px; font-size: 13px; color: #6c757d;">Ceci est un message automatique, merci de ne pas y r&eacute;pondre.</p>
<p style="margin: 0; font-size: 12px; color: #6c757d;">&copy; {% now "Y" %} Mediapass - Tous droits r&eacute;serv&eacute;s</p>
<p style="margin: 5px 0 0; font-size: 11px; color: #adb5bd;">Plateforme de gestion des r&eacute;servations</p>
</td>
</tr>
</table>
</td>
</tr>
</table>""",
        },
        "reservation_approved": {
            "subject": "Réservation approuvée — {{ product.name }}",
            "body_html": """<h2>Réservation approuvée</h2>
<p>Bonjour,</p>
<p>Votre réservation pour le produit <strong>{{ product.name }}</strong> a été approuvée.</p>
<p><strong>Détails :</strong></p>
<ul>
<li>Du : {{ reservation.start_date }}</li>
<li>Au : {{ reservation.end_date }}</li>
<li>Quantité : {{ reservation.quantity }}</li>
</ul>""",
        },
        "reservation_disapproved": {
            "subject": "Réservation désapprouvée — {{ product.name }}",
            "body_html": """<h2>Réservation désapprouvée</h2>
<p>Bonjour,</p>
<p>Votre réservation pour <strong>{{ product.name }}</strong> a été désapprouvée.</p>
<p><strong>Motif :</strong> {{ reason }}</p>
{% if comment %}<p><strong>Commentaire :</strong> {{ comment }}</p>{% endif %}""",
        },
        "structure_validated": {
            "subject": "Structure validée — {{ structure.name }}",
            "body_html": """<h2>Validation de votre structure</h2>
<p>Bonjour,</p>
<p>Nous vous informons que votre structure <strong>{{ structure.name }}</strong> a été validée.</p>
<p>Vous pouvez dès maintenant effectuer des réservations sur notre plateforme.</p>
<p>Cordialement,<br>L'équipe du réseau Médi@'pass</p>""",
        },
        "poster_request": {
            "subject": "Demande d'affiche — {{ workshop.name }}",
            "body_html": """<h2>Demande d'affiche pour un atelier</h2>
<p><strong>Atelier :</strong> {{ workshop.name }}</p>
<p><strong>Date :</strong> {{ workshop.date }}</p>
<p><strong>Lieu :</strong> {{ workshop.location.name }}</p>
<p><strong>Horaire :</strong> {{ workshop.start_time }} — {{ workshop.end_time }}</p>
{% if workshop.observations %}<p><strong>Observations :</strong><br>{{ workshop.observations|linebreaksbr }}</p>{% endif %}
<p>Une affiche est requise pour cet atelier. Merci de la préparer.</p>""",
        },
        "poster_validated": {
            "subject": "Affiche validée — {{ workshop.name }}",
            "body_html": """<h2>Affiche validée</h2>
<p>L'affiche de l'atelier <strong>{{ workshop.name }}</strong> a été validée.</p>""",
        },
        "poster_rejected": {
            "subject": "Affiche refusée — {{ workshop.name }}",
            "body_html": """<h2>Affiche refusée</h2>
<p>L'affiche de l'atelier <strong>{{ workshop.name }}</strong> a été refusée.</p>
{% if comment %}<p><strong>Motif :</strong> {{ comment }}</p>{% endif %}""",
        },
        "poster_image_uploaded": {
            "subject": "Nouvelle image d'affiche — {{ workshop.name }}",
            "body_html": """<h2>Image d'affiche ajoutée</h2>
<p>Une nouvelle image d'affiche a été ajoutée pour l'atelier <strong>{{ workshop.name }}</strong>.</p>
<p>Connectez-vous pour la valider.</p>""",
        },
        "reservation_reminder": {
            "subject": "Rappel : Réservation se terminant demain",
            "body_html": """<h2>Rappel de réservation</h2>
<p><strong>Produit :</strong> {{ reservation.product.name }}</p>
<p><strong>Structure :</strong> {{ reservation.structure.name }}</p>
<p><strong>Fin de réservation :</strong> {{ reservation.end_date }}</p>
<p>Pensez à retourner le matériel.</p>""",
        },
        "workshop_reminder": {
            "subject": "Rappel : Atelier demain — {{ workshop.title }}",
            "body_html": """<h2>Rappel d'atelier</h2>
<p><strong>Atelier :</strong> {{ workshop.title }}</p>
<p><strong>Date :</strong> {{ workshop.start_date }}</p>
<p><strong>Horaire :</strong> {{ workshop.start_time }} — {{ workshop.end_time }}</p>
<p><strong>Participants inscrits :</strong> {{ participant_count }}</p>""",
        },
    }

    for notif_type, data in defaults.items():
        EmailTemplate.objects.get_or_create(
            notification_type=notif_type,
            defaults={"subject": data["subject"], "body_html": data["body_html"]},
        )
