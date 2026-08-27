"""Vues de l'application newsletter (builder)."""

from calendar import monthrange
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from library_workshops.models import Workshop

from .decorators import (
    communication_required,
    fiche_edit_required,
    mediatheque_required,
)
from .forms import (
    BLOCK_TYPE_TO_FORM,
    EventForm,
    ImageForm,
    LibraryPickForm,
    NewsletterForm,
    SectionForm,
    SettingsForm,
    TextForm,
    WorkshopBlockForm,
)
from .models import Block, LibraryProfile, Newsletter, NewsletterImage, Section
from .services import (
    build_library_snapshot,
    build_workshop_snapshot,
    export_contacts_csv,
    get_candidate_workshops,
    push_to_sender,
    render_newsletter_email,
    sanitize_html,
)

DEFAULT_CONTENT = {
    "heading": {
        "text": "Un nouveau titre",
        "align": "left",
        "size": 28,
        "color": "#1e293b",
    },
    "text": {
        "html": "<p>Écrivez votre texte ici…</p>",
        "align": "left",
        "font_size": 15,
    },
    "image": {},
    "button": {"label": "En savoir plus", "url": "", "align": "center"},
    "separator": {"color": ""},
    "spacer": {"height": 24},
    "event": {"title": "Nouvel événement", "subtitle": "", "date_text": "", "body": ""},
    "workshop": {},
    "library": {},
}


def _next_month_range(today=None):
    today = today or now().date()
    year, month = (
        (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    )
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _canvas_response(request, newsletter, toast=None):
    html = render_to_string(
        "newsletter/partials/canvas.html",
        {"newsletter": newsletter, "site_url": settings.SITE_URL},
        request=request,
    )
    response = HttpResponse(html)
    if toast:
        response["HX-Trigger"] = f'{{"nl-toast": "{toast}"}}'
    return response


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@login_required
@communication_required
def index(request):
    newsletters = Newsletter.objects.prefetch_related("blocks")
    if request.method == "POST":
        form = NewsletterForm(request.POST)
        if form.is_valid():
            newsletter = form.save(commit=False)
            newsletter.created_by = request.user
            newsletter.save()
            messages.success(request, f"Newsletter « {newsletter.title} » créée.")
            return redirect("newsletter:builder", pk=newsletter.pk)
    else:
        start, end = _next_month_range()
        form = NewsletterForm(initial={"period_start": start, "period_end": end})
    return render(
        request, "newsletter/dashboard.html", {"newsletters": newsletters, "form": form}
    )


@login_required
@communication_required
@require_POST
def delete_newsletter(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    title = newsletter.title
    newsletter.delete()
    messages.success(request, f"Newsletter « {title} » supprimée.")
    return redirect("newsletter:index")


@login_required
@communication_required
@require_POST
def duplicate_newsletter(request, pk):
    original = get_object_or_404(Newsletter, pk=pk)
    copy = original.duplicate()
    messages.success(request, f"Newsletter dupliquée en « {copy.title} ».")
    return redirect("newsletter:builder", pk=copy.pk)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


CONTENT_BLOCK_TYPES = [
    {"key": "heading", "label": "Titre", "icon": "bx-header"},
    {"key": "text", "label": "Texte", "icon": "bx-text"},
    {"key": "image", "label": "Image", "icon": "bx-image-alt"},
    {"key": "button", "label": "Bouton", "icon": "bx-pointer"},
    {"key": "separator", "label": "Séparateur", "icon": "bx-minus"},
    {"key": "spacer", "label": "Espaceur", "icon": "bx-dots-vertical-rounded"},
]

SPECIAL_BLOCK_TYPES = [
    {
        "key": "workshop",
        "label": "Bloc atelier",
        "hint": "Depuis l'onglet Ateliers",
        "icon": "bx-calendar-star",
    },
    {
        "key": "event",
        "label": "Événement manuel",
        "hint": "Bannière + affiche + texte",
        "icon": "bx-party",
    },
    {
        "key": "library",
        "label": "Fiche médiathèque",
        "hint": "Horaires & infos pratiques",
        "icon": "bx-map",
    },
]


@login_required
@communication_required
def builder(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    context = {
        "newsletter": newsletter,
        "settings_form": SettingsForm(instance=newsletter),
        "candidate_groups": get_candidate_workshops(
            newsletter.period_start, newsletter.period_end
        ),
        "content_block_types": CONTENT_BLOCK_TYPES,
        "special_block_types": SPECIAL_BLOCK_TYPES,
        "sender_configured": bool(getattr(settings, "SENDER_API_KEY", "")),
        "site_url": settings.SITE_URL,
    }
    return render(request, "newsletter/builder.html", context)


@login_required
@communication_required
def candidates_panel(request, pk):
    """Panneau de choix de la fiche médiathèque à insérer."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(
        request,
        "newsletter/panels/candidates_panel.html",
        {"newsletter": newsletter, "pick_form": LibraryPickForm()},
    )


@login_required
@communication_required
def candidates_tab(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(
        request,
        "newsletter/partials/candidates.html",
        {
            "newsletter": newsletter,
            "candidate_groups": get_candidate_workshops(
                newsletter.period_start, newsletter.period_end
            ),
        },
    )


@login_required
@communication_required
def candidates_refresh(request, pk):
    """Recharge la période côté serveur puis renvoie l'onglet candidats."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    try:
        newsletter.period_start = date.fromisoformat(start)
        newsletter.period_end = date.fromisoformat(end)
        newsletter.save(update_fields=["period_start", "period_end"])
    except ValueError:
        pass
    return candidates_tab(request, pk)


@login_required
@communication_required
def settings_panel(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(
        request,
        "newsletter/panels/settings.html",
        {"newsletter": newsletter, "form": SettingsForm(instance=newsletter)},
    )


@login_required
@communication_required
@require_POST
def settings_update(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    form = SettingsForm(request.POST, instance=newsletter)
    if form.is_valid():
        form.save()
        newsletter.refresh_from_db()
        return _canvas_response(request, newsletter, "Paramètres enregistrés")
    errors = "; ".join(f"{f}: {e[0]}" for f, e in form.errors.items())
    return _canvas_response(request, newsletter, f"Erreur : {errors[:120]}")


# ---------------------------------------------------------------------------
# Blocs
# ---------------------------------------------------------------------------


def _create_block(newsletter, block_type, content=None, section=None, style=None):
    base_content = dict(DEFAULT_CONTENT.get(block_type, {}))
    if content:
        base_content.update(content)
    return Block.objects.create(
        newsletter=newsletter,
        section=section,
        position=Block.next_position(newsletter, section=section),
        block_type=block_type,
        content=base_content,
        style=style or {},
    )


def _create_section(
    newsletter, library_profile=None, title="", background_color="#ffffff"
):
    return Section.objects.create(
        newsletter=newsletter,
        position=Section.next_position(newsletter),
        library_profile=library_profile,
        title=title or (library_profile.name if library_profile else ""),
        background_color=background_color,
    )


@login_required
@communication_required
@require_POST
def add_block(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    block_type = request.POST.get("block_type", "")
    valid_types = {choice[0] for choice in Block._meta.get_field("block_type").choices}
    if block_type not in valid_types:
        return _canvas_response(request, newsletter, "Type de bloc inconnu")

    # section cible optionnelle (pour ajouter un bloc à l'intérieur d'une section)
    section = None
    section_id = request.POST.get("section_id")
    if section_id:
        section = Section.objects.filter(pk=section_id, newsletter=newsletter).first()

    content = {}
    if block_type == "workshop":
        workshop = Workshop.objects.filter(pk=request.POST.get("workshop_id")).first()
        if workshop is None:
            return _canvas_response(request, newsletter, "Atelier introuvable")
        already = (
            Block.objects.filter(
                newsletter=newsletter,
                block_type="workshop",
                content__workshop_id=str(workshop.pk),
            ).exists()
            or Block.objects.filter(
                newsletter=newsletter,
                block_type="workshop",
                content__workshop_id=workshop.pk,
            ).exists()
        )
        if already:
            return _canvas_response(
                request, newsletter, "Cet atelier est déjà dans la newsletter"
            )
        content = build_workshop_snapshot(workshop)
    elif block_type == "library":
        profile_id = request.POST.get("profile_id")
        profile = None
        if profile_id:
            profile = LibraryProfile.objects.filter(pk=profile_id).first()
        else:
            profile = LibraryProfile.objects.order_by("name").first()
        if profile is None:
            return _canvas_response(
                request, newsletter, "Aucune fiche médiathèque disponible"
            )
        content = build_library_snapshot(profile)

    _create_block(newsletter, block_type, content or None, section=section)
    labels = dict(Block._meta.get_field("block_type").choices)
    return _canvas_response(
        request, newsletter, f"Bloc « {labels[block_type]} » ajouté"
    )


@login_required
@communication_required
@require_POST
def bulk_add_workshops(request, pk):
    """Ajoute d'un coup tous les ateliers candidats, triés par médiathèque puis date."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    groups = get_candidate_workshops(newsletter.period_start, newsletter.period_end)

    def _group_key(g):
        prof = g.get("profile")
        if prof and prof.name:
            return prof.name.lower()
        return g["user"].username.lower()

    groups = sorted(groups, key=_group_key)
    # aplati tout en gardant le tri intra-groupe déjà par date
    ordered = []
    for g in groups:
        # tri intra-groupe par date/heure (déjà trié mais on re-trie pour robustesse)
        workshops_sorted = sorted(
            g["workshops"],
            key=lambda it: (it["workshop"].start_date, it["workshop"].start_time),
        )
        for item in workshops_sorted:
            ordered.append((g, item))

    if not ordered:
        return _canvas_response(
            request, newsletter, "Aucun atelier à ajouter pour cette période"
        )

    # collecte des workshop_id déjà présents pour éviter doublons
    existing_ids = set(
        Block.objects.filter(newsletter=newsletter, block_type="workshop").values_list(
            "content__workshop_id", flat=True
        )
    )
    # content__workshop_id peut être str ou int selon snapshot — normalise en str
    existing_str = {str(x) for x in existing_ids if x is not None}

    added = 0
    # map médiathèque -> Section existante (par library_profile ou titre) pour réutiliser
    existing_sections = {}
    for sec in newsletter.sections.all():
        key = sec.library_profile_id or sec.title.lower()
        existing_sections[key] = sec
    with transaction.atomic():
        for g, item in ordered:
            ws = item["workshop"]
            if str(ws.pk) in existing_str:
                continue
            prof = g.get("profile")
            heading_text = (
                prof.name
                if prof and prof.name
                else g["user"].get_full_name() or g["user"].username
            )
            # section par médiathèque (une seule, fond blanc uniforme par défaut)
            sec_key = prof.pk if prof else heading_text.lower()
            section = existing_sections.get(sec_key)
            if section is None:
                # cherche aussi par titre si profil manquant
                section = (
                    Section.objects.filter(
                        newsletter=newsletter, library_profile=prof
                    ).first()
                    if prof
                    else Section.objects.filter(
                        newsletter=newsletter, title=heading_text
                    ).first()
                )
            if section is None:
                section = _create_section(
                    newsletter,
                    library_profile=prof,
                    title=heading_text,
                    background_color="#ffffff",
                )
                existing_sections[sec_key] = section
                existing_sections[section.pk] = section
            _create_block(
                newsletter, "workshop", build_workshop_snapshot(ws), section=section
            )
            existing_str.add(str(ws.pk))
            added += 1

    if added == 0:
        return _canvas_response(
            request, newsletter, "Tous les ateliers étaient déjà présents"
        )
    return _canvas_response(
        request,
        newsletter,
        f"{added} atelier(s) ajoutés en sections — triés par médiathèque puis date",
    )


def _get_section(request, pk, section_id):
    return get_object_or_404(
        Section.objects.select_related("newsletter"), pk=section_id, newsletter__pk=pk
    )


def _get_block(request, pk, block_id):
    return get_object_or_404(
        Block.objects.select_related("newsletter", "section"),
        pk=block_id,
        newsletter__pk=pk,
    )


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


@login_required
@communication_required
@require_POST
def add_section(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    profile_id = request.POST.get("library_profile") or request.POST.get("profile_id")
    profile = (
        LibraryProfile.objects.filter(pk=profile_id).first() if profile_id else None
    )
    title = request.POST.get("title", "").strip()
    bg = request.POST.get("background_color", "#ffffff").strip() or "#ffffff"
    if profile and not title:
        title = profile.name
    sec = _create_section(
        newsletter, library_profile=profile, title=title, background_color=bg
    )
    return _canvas_response(
        request, newsletter, f"Section « {sec.title or 'sans titre'} » ajoutée"
    )


@login_required
@communication_required
def edit_section_panel(request, pk, section_id):
    section = _get_section(request, pk, section_id)
    form = SectionForm(instance=section)
    return render(
        request,
        "newsletter/panels/section_panel.html",
        {"newsletter": section.newsletter, "section": section, "form": form},
    )


@login_required
@communication_required
@require_POST
def update_section(request, pk, section_id):
    section = _get_section(request, pk, section_id)
    form = SectionForm(request.POST, instance=section)
    if not form.is_valid():
        error = next(iter(form.errors.values()))[0]
        return _canvas_response(
            request, section.newsletter, f"Non enregistré : {error}"
        )
    form.save()
    return _canvas_response(request, section.newsletter, "Section mise à jour")


@login_required
@communication_required
@require_POST
def move_section(request, pk, section_id, direction):
    section = _get_section(request, pk, section_id)
    moved = direction in ("up", "down") and section.move(direction)
    toast = "Section déplacée" if moved else "Impossible de déplacer cette section"
    return _canvas_response(request, section.newsletter, toast)


@login_required
@communication_required
@require_POST
def delete_section(request, pk, section_id):
    section = _get_section(request, pk, section_id)
    newsletter = section.newsletter
    section.delete()  # CASCADE supprime les blocs à l'intérieur
    return _canvas_response(request, newsletter, "Section supprimée")


@login_required
@communication_required
@require_POST
def reorder_sections(request, pk):
    """Réordonne les sections via drag & drop (JSON {order:[id,...]})."""
    import json

    newsletter = get_object_or_404(Newsletter, pk=pk)
    try:
        data = json.loads(request.body.decode() or "{}")
        order = data.get("order", [])
        if not isinstance(order, list):
            raise ValueError
    except Exception:
        return _canvas_response(request, newsletter, "Ordre invalide")
    # vérifie que toutes les ids appartiennent à cette newsletter
    sections = {s.pk: s for s in newsletter.sections.all()}
    if set(order) != set(sections.keys()) and order:
        # tolère ordre partiel (ex. après suppression) — on ne traite que les présents
        order = [oid for oid in order if oid in sections]
    with transaction.atomic():
        for idx, sid in enumerate(order):
            sec = sections.get(sid)
            if sec and sec.position != idx:
                Section.objects.filter(pk=sid).update(position=idx)
    return _canvas_response(request, newsletter, "Sections réordonnées")


@login_required
@communication_required
@require_POST
def clear_layout(request, pk):
    """Vide toute la mise en page : supprime blocs et sections (garde la newsletter)."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    with transaction.atomic():
        Block.objects.filter(newsletter=newsletter).delete()
        Section.objects.filter(newsletter=newsletter).delete()
    return _canvas_response(
        request, newsletter, "Mise en page vidée — tous les blocs ont été supprimés"
    )


@login_required
@communication_required
@require_POST
def reorder_blocks(request, pk):
    """Réordonne les blocs (supporte drag inter-sections). JSON {blocks:{section_id:[block_ids]}} section_id "null" pour orphelins."""
    import json

    newsletter = get_object_or_404(Newsletter, pk=pk)
    try:
        data = json.loads(request.body.decode() or "{}")
        blocks_map = data.get("blocks", {})
        if not isinstance(blocks_map, dict):
            raise ValueError
    except Exception:
        return _canvas_response(request, newsletter, "Ordre invalide")
    with transaction.atomic():
        for sec_key, ids in blocks_map.items():
            # sec_key = "null" ou str(section_id)
            if sec_key == "null" or sec_key is None or sec_key == "":
                section = None
            else:
                try:
                    section = Section.objects.get(
                        pk=int(sec_key), newsletter=newsletter
                    )
                except (Section.DoesNotExist, ValueError):
                    continue
            for pos, bid in enumerate(ids):
                try:
                    bid_int = int(bid)
                except ValueError:
                    continue
                Block.objects.filter(pk=bid_int, newsletter=newsletter).update(
                    section=section, position=pos
                )
    return _canvas_response(request, newsletter, "Blocs réordonnés")


@login_required
@communication_required
def edit_panel(request, pk, block_id):
    block = _get_block(request, pk, block_id)
    form_class = BLOCK_TYPE_TO_FORM.get(block.block_type)
    initial = dict(block.content)
    form = None
    if form_class is not None:
        form = form_class(initial=initial)
    return render(
        request,
        "newsletter/panels/edit_panel.html",
        {"newsletter": block.newsletter, "block": block, "form": form},
    )


@login_required
@communication_required
@require_POST
def update_block(request, pk, block_id):
    block = _get_block(request, pk, block_id)
    newsletter = block.newsletter
    form_class = BLOCK_TYPE_TO_FORM.get(block.block_type)

    style = {}
    if request.POST.get("style_bg_transparent"):
        style["bg_color"] = "transparent"
    else:
        v = request.POST.get("style_bg_color", "").strip()
        if v:
            style["bg_color"] = v.lower()
    for key, field_name in (
        ("text_color", "style_text_color"),
        ("padding", "style_padding"),
        ("border_style", "style_border_style"),
        ("border_color", "style_border_color"),
        ("border_width", "style_border_width"),
        ("border_radius", "style_border_radius"),
    ):
        value = request.POST.get(field_name, "").strip()
        if value:
            style[key] = value.lower() if "color" in key else value
    # normalisation couleur bordure en minuscule déjà faite
    if "border_color" in style:
        style["border_color"] = style["border_color"].lower()

    with transaction.atomic():
        if form_class is not None:
            form = form_class(request.POST, request.FILES)
            if not form.is_valid():
                error = next(iter(form.errors.values()))[0]
                return _canvas_response(
                    request, newsletter, f"Non enregistré : {error}"
                )

            data = form.cleaned_data
            if isinstance(form, WorkshopBlockForm):
                data["description"] = sanitize_html(data["description"])
                # couleurs titres/textes par bloc -> style (héritage section/global)
                title_color = data.pop("title_color", "")
                text_color = data.pop("text_color", "")
                if title_color:
                    style["title_color"] = title_color
                if text_color:
                    style["text_color"] = text_color
                image_file = data.pop("new_image", None)
                if image_file:
                    image = NewsletterImage.objects.create(
                        image=image_file,
                        alt=data["title"],
                        uploaded_by=request.user,
                    )
                    data["image_id"] = image.pk
                elif block.content.get("image_id"):
                    data["image_id"] = block.content["image_id"]
                # workshop_id est conservé tel quel pour traçabilité, non éditable
                if block.content.get("workshop_id"):
                    data["workshop_id"] = block.content["workshop_id"]
                if block.content.get("image_url") and "image_url" not in data:
                    data["image_url"] = block.content["image_url"]
            elif isinstance(form, TextForm):
                data["html"] = sanitize_html(data["html"])
            elif isinstance(form, EventForm):
                data["body"] = sanitize_html(data["body"])
                image_file = data.pop("new_image", None)
                if image_file:
                    image = NewsletterImage.objects.create(
                        image=image_file, alt=data["title"], uploaded_by=request.user
                    )
                    data["image_id"] = image.pk
                elif block.content.get("image_id"):
                    data["image_id"] = block.content["image_id"]
            elif isinstance(form, ImageForm):
                image_file = data.pop("new_image", None)
                if image_file:
                    image = NewsletterImage.objects.create(
                        image=image_file,
                        alt=data.get("alt", ""),
                        uploaded_by=request.user,
                    )
                    data["image_id"] = image.pk
                elif block.content.get("image_id"):
                    data["image_id"] = block.content["image_id"]
                    # Met à jour l'alt du fichier existant si modifié
                    try:
                        existing = NewsletterImage.objects.get(pk=data["image_id"])
                        if existing.alt != data.get("alt", ""):
                            existing.alt = data.get("alt", "")
                            existing.save(update_fields=["alt"])
                    except NewsletterImage.DoesNotExist:
                        pass

            block.content = data

        # Apparence (fond / couleur du texte / marge), même sans formulaire dédié.
        block.style = style
        block.save()

    return _canvas_response(request, newsletter, "Bloc mis à jour")


@login_required
@communication_required
@require_POST
def move_block(request, pk, block_id, direction):
    block = _get_block(request, pk, block_id)
    moved = direction in ("up", "down") and block.move(direction)
    toast = "Bloc déplacé" if moved else "Impossible de déplacer ce bloc"
    return _canvas_response(request, block.newsletter, toast)


@login_required
@communication_required
@require_POST
def duplicate_block(request, pk, block_id):
    block = _get_block(request, pk, block_id)
    block.duplicate()
    return _canvas_response(request, block.newsletter, "Bloc dupliqué")


@login_required
@communication_required
@require_POST
def delete_block(request, pk, block_id):
    block = _get_block(request, pk, block_id)
    newsletter = block.newsletter
    block.delete()
    return _canvas_response(request, newsletter, "Bloc supprimé")


# ---------------------------------------------------------------------------
# Exports & Sender.net
# ---------------------------------------------------------------------------


@login_required
@communication_required
def preview(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return HttpResponse(render_newsletter_email(newsletter), content_type="text/html")


@login_required
@communication_required
def download(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    filename = f"{slugify(newsletter.title) or 'newsletter'}.html"
    response = HttpResponse(
        render_newsletter_email(newsletter), content_type="text/html"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@communication_required
def contacts_csv(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    filename = f"contacts_{slugify(newsletter.title) or 'newsletter'}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff" + export_contacts_csv(newsletter))
    return response


@login_required
@communication_required
@require_POST
def send_sender(request, pk):
    newsletter = get_object_or_404(Newsletter, pk=pk)
    success, message = push_to_sender(newsletter)
    messages.add_message(
        request,
        messages.SUCCESS if success else messages.ERROR,
        message,
    )
    return redirect("newsletter:builder", pk=pk)


# ---------------------------------------------------------------------------
# Fiches médiathèques
# ---------------------------------------------------------------------------


class LibraryProfileForm(forms.ModelForm):
    class Meta:
        model = LibraryProfile
        fields = [
            "name",
            "image",
            "description",
            "phone",
            "address",
            "opening_hours",
            "closures",
            "website",
            "facebook_url",
            "instagram_url",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "nl-input"}),
            "description": forms.Textarea(attrs={"class": "nl-input", "rows": 3}),
            "phone": forms.TextInput(attrs={"class": "nl-input"}),
            "address": forms.TextInput(attrs={"class": "nl-input"}),
            "opening_hours": forms.Textarea(attrs={"class": "nl-input", "rows": 7}),
            "closures": forms.Textarea(attrs={"class": "nl-input", "rows": 3}),
            "website": forms.URLInput(
                attrs={"class": "nl-input", "placeholder": "https://"}
            ),
            "facebook_url": forms.URLInput(
                attrs={"class": "nl-input", "placeholder": "https://facebook.com/..."}
            ),
            "instagram_url": forms.URLInput(
                attrs={"class": "nl-input", "placeholder": "https://instagram.com/..."}
            ),
        }


@login_required
@communication_required
def fiche_list(request):
    profiles = LibraryProfile.objects.select_related("user").order_by("name")
    return render(request, "newsletter/fiche_list.html", {"profiles": profiles})


@login_required
@mediatheque_required
def ma_fiche(request):
    profile = LibraryProfile.objects.filter(user=request.user).first()
    if profile is None:
        profile = LibraryProfile(user=request.user, name="")
    return _render_fiche_form(request, profile, created=profile.pk is None)


@login_required
@fiche_edit_required
def fiche_edit(request, profile_id):
    profile = get_object_or_404(LibraryProfile, pk=profile_id)
    return _render_fiche_form(request, profile, created=False)


def _render_fiche_form(request, profile, created):
    if request.method == "POST":
        form = LibraryProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            saved = form.save(commit=False)
            if not saved.user_id:
                saved.user = request.user
            saved.save()
            messages.success(request, "Fiche médiathèque enregistrée.")
            return redirect("newsletter:ma_fiche")
    else:
        form = LibraryProfileForm(instance=profile)
    return render(
        request,
        "newsletter/fiche_form.html",
        {"form": form, "profile": profile, "created": created},
    )
