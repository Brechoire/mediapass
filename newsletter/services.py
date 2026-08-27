"""Services métier de l'application newsletter."""

import csv
import logging
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone
from library_workshops.models import Workshop, WorkshopParticipant
from library_workshops.services import NewsletterService as LegacyNewsletterService

from .models import Block, LibraryProfile, Newsletter

logger = logging.getLogger(__name__)

SENDER_API_URL = "https://api.sender.net/v2/campaigns"

# Balises/attributs autorisés dans le texte enrichi des blocs.
ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "a",
    "h2",
    "h3",
]
ALLOWED_ATTRS = {"a": ["href", "title", "target", "rel"]}


def sanitize_html(raw_html):
    """Nettoie le HTML riche saisi par l'éditeur (anti-XSS, whitelist)."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed = ALLOWED_ATTRS.get(tag.name, [])
        for attr in list(tag.attrs):
            if attr not in allowed:
                del tag.attrs[attr]
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if not href.lower().startswith(("http://", "https://", "mailto:")):
            a.attrs.pop("href", None)
        a["rel"] = "noopener"
    return str(soup)


def get_candidate_workshops(period_start, period_end):
    """Ateliers à proposer dans la newsletter pour la période donnée.

    Retourne une liste ordonnée de dicts : {"profile", "user", "workshops"}
    regroupée par médiathèque (created_by), triée par nom puis par date.
    """
    workshops = (
        Workshop.objects.filter(
            newsletter=True,
            status="active",
            start_date__gte=period_start,
            start_date__lte=period_end,
        )
        .select_related("created_by", "location")
        .order_by("start_date", "start_time")
    )

    grouped = OrderedDict()
    for workshop in workshops:
        key = workshop.created_by_id
        if key not in grouped:
            profile = LibraryProfile.objects.filter(user=workshop.created_by).first()
            grouped[key] = {
                "profile": profile,
                "user": workshop.created_by,
                "workshops": [],
            }
        grouped[key]["workshops"].append(
            {
                "workshop": workshop,
                "date_text": LegacyNewsletterService.format_date(workshop),
            }
        )

    return sorted(grouped.values(), key=lambda g: (g["profile"] or g["user"]).pk)


def build_workshop_snapshot(workshop, variant="inherit", image_width=140):
    """Instantané des données d'un atelier stockées dans le bloc.

    `variant` vaut "card"|"side"|"inherit" (hérite du défaut global).
    `image_width` : pour "side" = px (80-220), pour "card" = % (25/50/75/100) — ratio toujours conservé.
    """
    image_url = ""
    for attr_name in ("poster", "image"):
        image_field = getattr(workshop, attr_name, None)
        if image_field:
            try:
                image_url = image_field.url
                break
            except ValueError:
                continue
    location_name = workshop.location.name if workshop.location else ""
    return {
        "workshop_id": workshop.pk,
        "title": workshop.title,
        "date_text": LegacyNewsletterService.format_date(workshop),
        "description": workshop.description,
        "location": location_name,
        "image_url": image_url,
        "variant": variant,
        "image_width": image_width,
    }


def build_library_snapshot(profile):
    """Instantané des données d'une fiche médiathèque stockées dans le bloc."""
    image_url = ""
    if profile and profile.image:
        try:
            image_url = profile.image.url
        except ValueError:
            image_url = ""
    return {
        "profile_id": profile.pk if profile else None,
        "name": profile.name if profile else "",
        "description": profile.description if profile else "",
        "phone": profile.phone if profile else "",
        "address": profile.address if profile else "",
        "hours_lines": profile.hours_lines if profile else [],
        "closure_lines": profile.closure_lines if profile else [],
        "image_url": image_url,
    }


def get_block_image(block):
    """Récupère l'objet NewsletterImage référencé par un bloc, s'il existe."""
    from .models import NewsletterImage

    image_id = block.content.get("image_id")
    if not image_id:
        return None
    return NewsletterImage.objects.filter(pk=image_id).first()


def _style_of(block):
    return block.style or {}


def render_newsletter_email(newsletter):
    """Rend le HTML complet de l'email (table-based, styles inline)."""
    from django.template.loader import render_to_string

    rendered_blocks = []
    # Sections d'abord (fond uniforme), avec header + blocs dedans
    for section in newsletter.sections.all().prefetch_related("blocks"):
        # header de section
        rendered_blocks.append(
            render_to_string(
                "newsletter/partials/section_header.html",
                {
                    "section": section,
                    "newsletter": newsletter,
                    "site_url": settings.SITE_URL,
                    "for_email": True,
                },
            )
        )
        for block in section.blocks.all():
            rendered_blocks.append(
                render_to_string(
                    f"newsletter/partials/blocks/{block.block_type}.html",
                    {
                        "block": block,
                        "newsletter": newsletter,
                        "site_url": settings.SITE_URL,
                        "for_email": True,
                    },
                )
            )
    # Blocs orphelins (compatibilité legacy, hors sections)
    for block in newsletter.blocks.filter(section__isnull=True):
        rendered_blocks.append(
            render_to_string(
                f"newsletter/partials/blocks/{block.block_type}.html",
                {
                    "block": block,
                    "newsletter": newsletter,
                    "site_url": settings.SITE_URL,
                    "for_email": True,
                },
            )
        )
    return render_to_string(
        "newsletter/email/newsletter_email.html",
        {
            "newsletter": newsletter,
            "rendered_blocks": rendered_blocks,
            "site_url": settings.SITE_URL,
        },
    )


def export_contacts_csv(newsletter):
    """Contacts (nom, prénom, email) des inscrits aux ateliers de la période.

    Emails dédupliqués (insensible à la casse), triés par nom.
    """
    participants = (
        WorkshopParticipant.objects.filter(
            status="confirmed",
            email__isnull=False,
            workshop__status="active",
            workshop__start_date__gte=newsletter.period_start,
            workshop__start_date__lte=newsletter.period_end,
        )
        .select_related("workshop")
        .order_by("last_name", "first_name")
    )

    seen = set()
    rows = []
    for participant in participants:
        email_key = participant.email.strip().lower()
        if not email_key or email_key in seen:
            continue
        seen.add(email_key)
        rows.append((participant.last_name, participant.first_name, participant.email))

    lines = ["Nom;Prénom;Email"]
    for last_name, first_name, email in rows:
        lines.append(_csv_line(last_name, first_name, email))
    return "\r\n".join(lines) + "\r\n"


def _csv_line(*values):
    """Ligne CSV point-virgule (Excel FR), échappement minimal."""
    escaped = []
    for value in values:
        value = (value or "").strip()
        if ";" in value or '"' in value or "\n" in value:
            value = '"' + value.replace('"', '""') + '"'
        escaped.append(value)
    return ";".join(escaped)


def push_to_sender(newsletter):
    """Crée une campagne en brouillon sur Sender.net.

    Retourne (succès: bool, message: str).
    """
    api_key = getattr(settings, "SENDER_API_KEY", "")
    if not api_key:
        return False, (
            "Clé API Sender.net manquante. Renseignez SENDER_API_KEY dans le .env."
        )

    reply_to = getattr(settings, "SENDER_REPLY_TO", "") or getattr(
        settings, "DEFAULT_FROM_EMAIL", ""
    )
    from_name = getattr(settings, "SENDER_FROM_NAME", "Médi@'pass")

    payload = {
        "title": newsletter.title,
        "subject": newsletter.subject,
        "preheader": newsletter.preheader or "",
        "from": from_name,
        "reply_to": reply_to,
        "content_type": "html",
        "content": render_newsletter_email(newsletter),
    }
    group_id = getattr(settings, "SENDER_GROUP_ID", "")
    if group_id:
        payload["groups"] = [group_id]

    try:
        response = requests.post(
            SENDER_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.error("Sender.net injoignable : %s", exc)
        return False, f"Impossible de joindre Sender.net : {exc}"

    if response.status_code >= 400:
        logger.error(
            "Erreur Sender.net %s : %s", response.status_code, response.text[:500]
        )
        return False, (
            f"Sender.net a refusé la campagne (HTTP {response.status_code}) : "
            f"{response.text[:200]}"
        )

    data = {}
    try:
        data = response.json() or {}
    except ValueError:
        pass
    campaign_id = (data.get("data") or {}).get("id", "")
    newsletter.sender_campaign_id = campaign_id or "-"
    newsletter.sender_pushed_at = timezone.now()
    newsletter.status = Newsletter.Status.SENT
    newsletter.save(update_fields=["sender_campaign_id", "sender_pushed_at", "status"])
    return True, "Campagne créée en brouillon sur Sender.net."
