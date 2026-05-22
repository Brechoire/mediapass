"""Services pour l'envoi d'emails de notification.

Ce module contient les fonctions pour envoyer des emails de notification,
notamment les rappels de réservation.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_reservation_reminder_email(reservation, recipients):
    """Envoie un email de rappel pour une réservation se terminant demain.

    Args:
        reservation: Instance du modèle Reservation
        recipients: Liste des adresses email destinataires

    Returns:
        bool: True si l'email a été envoyé avec succès, False sinon
    """
    if not recipients:
        return False

    subject = "Rappel : Réservation se terminant demain"
    from_email = settings.DEFAULT_FROM_EMAIL

    # Préparer le contexte pour le template
    context = {
        "reservation": reservation,
        "product": reservation.product,
        "structure": reservation.structure,
    }

    # Rendre le template HTML
    html_content = render_to_string(
        "notifications/reservation_reminder_email.html",
        context,
    )
    text_content = strip_tags(html_content)

    # Créer l'email avec HTML et texte
    email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        recipients,
    )
    email.attach_alternative(html_content, "text/html")

    # Envoyer l'email
    try:
        email.send()
        return True
    except Exception as e:
        # Log l'erreur si nécessaire
        print(f"Erreur lors de l'envoi de l'email de rappel: {e}")
        return False


def send_workshop_reminder_email(workshop, participants, recipients):
    """Envoie un email de rappel J-1 pour un atelier.

    Args:
        workshop: Instance du modèle Workshop
        participants: Liste des participants confirmés (avec email)
        recipients: Liste des adresses email destinataires admin

    Returns:
        bool: True si l'email a été envoyé avec succès, False sinon
    """
    if not recipients:
        return False

    subject = f"Rappel : Atelier demain — {workshop.title}"
    from_email = settings.DEFAULT_FROM_EMAIL

    context = {
        "workshop": workshop,
        "participants": participants,
        "participant_count": len(participants),
    }

    html_content = render_to_string(
        "notifications/workshop_reminder_email.html",
        context,
    )
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        recipients,
    )
    email.attach_alternative(html_content, "text/html")

    try:
        email.send()
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi du rappel d'atelier: {e}")
        return False

