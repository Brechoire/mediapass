"""Service centralisé pour l'envoi d'emails de notification.

Ce module remplace tous les appels directs à send_mail() et EmailMultiAlternatives()
dispersés dans les vues. Les destinataires et templates sont gérés depuis l'admin.
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

from .models import EmailTemplate, NotificationRecipient

logger = logging.getLogger(__name__)


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
            "body_html": """<h2>Nouvelle demande de réservation</h2>
<p><strong>Produit :</strong> {{ product.name }}</p>
<p><strong>Structure :</strong> {{ reservation.structure.name }}</p>
<p><strong>Dates :</strong> du {{ reservation.start_date }} au {{ reservation.end_date }}</p>
<p><strong>Quantité :</strong> {{ reservation.quantity }}</p>
<p>Connectez-vous à l'interface d'administration pour gérer cette réservation.</p>""",
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
