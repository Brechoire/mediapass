import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .models import EmailTemplate, NotificationRecipient
from .email_service import _render_template_string

logger = logging.getLogger(__name__)


def is_superuser(user):
    return user.is_superuser


@user_passes_test(is_superuser)
def email_admin(request):
    templates = EmailTemplate.objects.all().order_by("notification_type")
    recipients = NotificationRecipient.objects.select_related().all().order_by("-created_at")
    return render(request, "notifications/email_admin.html", {
        "templates": templates,
        "recipients": recipients,
    })


@user_passes_test(is_superuser)
def email_template_edit(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk)
    if request.method == "POST":
        if "test_send" in request.POST:
            return _send_test_email(request, template)
        subject = request.POST.get("subject", "").strip()
        body_html = request.POST.get("body_html", "").strip()
        if subject and body_html:
            template.subject = subject
            template.body_html = body_html
            template.is_active = request.POST.get("is_active") == "on"
            template.save()
            messages.success(request, f"Template '{template.get_notification_type_display()}' mis à jour.")
            return redirect("notifications:email_admin")
        else:
            messages.error(request, "Le sujet et le corps ne peuvent pas être vides.")
    return render(request, "notifications/email_template_form.html", {
        "template": template,
    })


def _send_test_email(request, template):
    """Envoie un email de test à l'utilisateur connecté."""
    if not request.user.email:
        messages.error(request, "Vous n'avez pas d'adresse email renseignée sur votre compte.")
        return render(request, "notifications/email_template_form.html", {"template": template})

    context = {
        "product": {"name": "Produit test", "description": "Description test"},
        "reservation": {
            "start_date": "01/06/2026",
            "end_date": "05/06/2026",
            "quantity": 2,
            "structure": {"name": "Structure test"},
        },
        "workshop": {
            "name": "Atelier test",
            "title": "Atelier test",
            "date": "15/06/2026",
            "start_time": "14:00",
            "end_time": "16:00",
            "location": {"name": "Médiathèque"},
        },
        "structure": {"name": "Structure test"},
        "reason": "Test",
        "comment": "Ceci est un test d'envoi",
        "participant_count": 5,
        "site_url": settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost",
    }

    try:
        subject = _render_template_string(template.subject, context)
        html_content = _render_template_string(template.body_html, context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            f"[TEST] {subject}",
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        messages.success(request, f"Email de test envoyé à {request.user.email}.")
    except Exception as e:
        logger.error("Erreur envoi test: %s", str(e))
        messages.error(request, f"Erreur lors de l'envoi : {str(e)}")

    return render(request, "notifications/email_template_form.html", {"template": template})


@user_passes_test(is_superuser)
def recipient_add(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        notification_type = request.POST.get("notification_type", "").strip()
        is_active = request.POST.get("is_active") == "on"
        if email and notification_type:
            _, created = NotificationRecipient.objects.get_or_create(
                email=email,
                notification_type=notification_type,
                defaults={"is_active": is_active},
            )
            if created:
                messages.success(request, f"Destinataire {email} ajouté.")
            else:
                messages.info(request, f"Cet email existe déjà pour ce type.")
            return redirect("notifications:email_admin")
        else:
            messages.error(request, "L'email et le type sont obligatoires.")
    return render(request, "notifications/recipient_form.html", {
        "recipient": None,
        "types": EmailTemplate.NOTIFICATION_TYPES,
    })


@user_passes_test(is_superuser)
def recipient_edit(request, pk):
    recipient = get_object_or_404(NotificationRecipient, pk=pk)
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        notification_type = request.POST.get("notification_type", "").strip()
        is_active = request.POST.get("is_active") == "on"
        if email and notification_type:
            recipient.email = email
            recipient.notification_type = notification_type
            recipient.is_active = is_active
            recipient.save()
            messages.success(request, "Destinataire mis à jour.")
            return redirect("notifications:email_admin")
        else:
            messages.error(request, "L'email et le type sont obligatoires.")
    return render(request, "notifications/recipient_form.html", {
        "recipient": recipient,
        "types": EmailTemplate.NOTIFICATION_TYPES,
    })


@require_POST
@user_passes_test(is_superuser)
def recipient_delete(request, pk):
    recipient = get_object_or_404(NotificationRecipient, pk=pk)
    email = recipient.email
    recipient.delete()
    messages.success(request, f"Destinataire {email} supprimé.")
    return redirect("notifications:email_admin")
