from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Count, Q, Prefetch, Max
from django.db.models.functions import ExtractYear
from django.template.loader import render_to_string
import time
import logging

from .models import Workshop, WorkshopParticipant, RecurrencePattern
from .forms import (
    WorkshopForm,
    WorkshopParticipantForm,
    WorkshopGroupReservationForm,
    QuickLocationForm,
    RecurrenceForm,
)
from .services import WorkshopStatisticsService, NewsletterService
from .recurrence import RecurrenceService
from .decorators import mediatheque_member_required, mediatheque_member_required_json
from .utils import filter_owned, filter_location_owned
from visitor_tracking.models import Location as VisitorLocation

logger = logging.getLogger(__name__)


@login_required
@mediatheque_member_required
def index(request):
    upcoming_workshops = (
        filter_owned(
            Workshop.objects.filter(start_date__gte=timezone.now().date()), request.user
        )
        .annotate(
            confirmed_count=Count(
                "participants", filter=Q(participants__status="confirmed")
            ),
            waiting_count=Count(
                "participants", filter=Q(participants__status="waiting")
            ),
        )
        .select_related("location")
        .order_by("start_date", "start_time")[:10]
    )

    return render(
        request, "library_workshops/index.html", {"workshops": upcoming_workshops}
    )


@login_required
@mediatheque_member_required
def create_workshop(request):
    if request.method == "POST":
        form = WorkshopForm(request.POST, request.FILES, user=request.user)
        recurrence_form = RecurrenceForm(request.POST)

        if form.is_valid():
            is_recurring = (
                request.POST.get("is_recurring") == "on" and recurrence_form.is_valid()
            )

            if is_recurring:
                pattern = recurrence_form.save(commit=False)
                cd = form.cleaned_data
                pattern.start_time = cd["start_time"]
                pattern.end_time = cd["end_time"]
                pattern.title = cd["title"]
                pattern.description = cd["description"]
                pattern.location = cd["location"]
                pattern.max_participants = cd["max_participants"]
                pattern.is_all_ages = cd["is_all_ages"]
                pattern.min_age = cd["min_age"]
                pattern.max_age = cd["max_age"]
                pattern.newsletter = cd["newsletter"]
                pattern.is_class_welcome = cd["is_class_welcome"]
                dates = RecurrenceService.generate_dates(pattern)
                if not dates:
                    messages.error(
                        request,
                        "Aucune date générée. Vérifiez les paramètres de récurrence.",
                    )
                    return render(
                        request,
                        "library_workshops/workshop_form.html",
                        {
                            "form": form,
                            "recurrence_form": recurrence_form,
                            "title": "Créer un nouvel atelier",
                        },
                    )
                RecurrenceService.create_workshops(request, pattern, dates)
                messages.success(request, f"{len(dates)} ateliers créés avec succès !")
            else:
                workshop = form.save(commit=False)
                workshop.created_by = request.user
                workshop.save()
                check_workshop_conflicts(workshop, request)
                check_duplicate_title(workshop, request)
                messages.success(request, "L'atelier a été créé avec succès !")

            return redirect("library_workshops:index")
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = WorkshopForm(user=request.user)
        recurrence_form = RecurrenceForm()

    return render(
        request,
        "library_workshops/workshop_form.html",
        {
            "form": form,
            "recurrence_form": recurrence_form,
            "title": "Créer un nouvel atelier",
        },
    )


def check_workshop_conflicts(workshop, request):
    conflicts = Workshop.objects.filter(
        location=workshop.location,
        newsletter=True,
    ).exclude(pk=workshop.pk)

    date_overlap = Q(
        start_date__lte=workshop.start_date, end_date__gte=workshop.start_date
    )
    if workshop.end_date:
        date_overlap |= Q(
            start_date__lte=workshop.end_date, end_date__gte=workshop.end_date
        )
        date_overlap |= Q(
            start_date__gte=workshop.start_date, end_date__lte=workshop.end_date
        )
    else:
        date_overlap |= Q(start_date=workshop.start_date)

    conflicts = conflicts.filter(date_overlap)

    time_overlap = Q(start_time__lt=workshop.end_time, end_time__gt=workshop.start_time)
    conflicts = conflicts.filter(time_overlap)

    for conflict in conflicts:
        messages.warning(
            request,
            f"Attention : l'atelier « {conflict.title} » ({conflict.start_date}) est programmé au même moment au même lieu.",
        )


def check_duplicate_title(workshop, request):
    same_title = Workshop.objects.filter(title__iexact=workshop.title).exclude(
        pk=workshop.pk
    )
    if same_title.exists():
        messages.warning(
            request,
            f"Attention : un atelier avec le même titre « {workshop.title} » existe déjà.",
        )


def _edit_recurrence_pattern(request, pattern):
    """Édition de tous les ateliers futurs d'un pattern de récurrence."""
    if request.method == "POST":
        form = WorkshopForm(request.POST, request.FILES, user=request.user)
        recurrence_form = RecurrenceForm(request.POST, instance=pattern)
        edit_action = request.POST.get("edit_action", "all_future")

        if form.is_valid() and recurrence_form.is_valid():
            cd = form.cleaned_data
            new_data = {
                "title": cd["title"],
                "description": cd["description"],
                "start_time": cd["start_time"],
                "end_time": cd["end_time"],
                "location": cd["location"],
                "max_participants": cd["max_participants"],
                "is_all_ages": cd["is_all_ages"],
                "min_age": cd["min_age"],
                "max_age": cd["max_age"],
                "newsletter": cd["newsletter"],
                "is_class_welcome": cd["is_class_welcome"],
            }
            recd = recurrence_form.cleaned_data
            new_data.update(
                {
                    "frequency": recd.get("frequency"),
                    "interval": recd.get("interval"),
                    "days_of_week": recd.get("days_of_week", []),
                    "period_start": recd.get("period_start"),
                    "period_end": recd.get("period_end"),
                    "excluded_dates": recd.get("excluded_dates", []),
                    "month_day": recd.get("month_day"),
                }
            )

            if edit_action == "all":
                Workshop.objects.filter(
                    recurrence_group=pattern, recurrence_modified=False
                ).delete()
                pattern.workshops.exclude(recurrence_modified=True).delete()

            RecurrenceService.update_future_workshops(request, pattern, new_data)
            messages.success(request, "La série d'ateliers a été mise à jour.")
            return redirect("library_workshops:index")
    else:
        data = {
            "title": pattern.title,
            "description": pattern.description,
            "start_time": pattern.start_time,
            "end_time": pattern.end_time,
            "location": pattern.location,
            "max_participants": pattern.max_participants,
            "is_all_ages": pattern.is_all_ages,
            "min_age": pattern.min_age,
            "max_age": pattern.max_age,
            "newsletter": pattern.newsletter,
            "is_class_welcome": pattern.is_class_welcome,
        }
        form = WorkshopForm(initial=data, user=request.user)
        recurrence_form = RecurrenceForm(instance=pattern)

    return render(
        request,
        "library_workshops/workshop_form.html",
        {
            "form": form,
            "recurrence_form": recurrence_form,
            "title": f"Modifier la série : {pattern.title}",
            "editing_recurrence": True,
        },
    )


@login_required
@mediatheque_member_required
def recurrence_preview(request):
    """Endpoint HTMX : retourne l'aperçu des dates générées."""
    from .recurrence import RecurrenceService
    from .models import SchoolHoliday

    if request.method == "POST":
        freq = request.POST.get("frequency")
        interval = request.POST.get("interval", 1)
        days_raw = request.POST.get("days_of_week", "[]")
        period_start = request.POST.get("period_start")
        period_end = request.POST.get("period_end")
        month_day = request.POST.get("month_day")
        exclude_holidays = request.POST.get("exclude_holidays")

        import json

        try:
            days = json.loads(days_raw)
        except (json.JSONDecodeError, TypeError):
            days = []

        if not period_start or not period_end:
            return JsonResponse({"dates": [], "count": 0, "html": ""})

        pattern = RecurrencePattern(
            frequency=freq,
            interval=int(interval) if interval else 1,
            days_of_week=days,
            period_start=date_type.fromisoformat(period_start),
            period_end=date_type.fromisoformat(period_end),
            month_day=int(month_day) if month_day else None,
            excluded_dates=[],
        )

        dates = RecurrenceService.generate_dates(pattern)

        # Exclure les vacances si demandé
        excluded_by_holidays = []
        if exclude_holidays == "B":
            holidays = SchoolHoliday.objects.filter(zone="B")
            filtered = []
            for d in dates:
                is_holiday = any(h.start_date <= d <= h.end_date for h in holidays)
                if is_holiday:
                    excluded_by_holidays.append(d.isoformat())
                else:
                    filtered.append(d)
            dates = filtered

        html = "".join(
            f'<span class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium '
            f'bg-green-50 text-green-700 border border-green-200" '
            f'data-date="{d.isoformat()}">'
            f'{d.strftime("%d/%m/%Y")} {d.strftime("%a")}</span> '
            for d in dates[:100]
        )
        if len(dates) > 100:
            html += f'<span class="text-xs text-[#b0bedb]">… et {len(dates) - 100} autres</span>'

        return JsonResponse(
            {
                "dates": [d.isoformat() for d in dates],
                "excluded_by_holidays": excluded_by_holidays,
                "count": len(dates),
                "html": html,
            }
        )

    return JsonResponse({"dates": [], "count": 0, "html": ""})


@login_required
@mediatheque_member_required
def recurrence_holidays(request):
    """Endpoint JSON : retourne les dates de vacances pour une zone."""
    zone = request.GET.get("zone", "B")
    holidays = SchoolHoliday.objects.filter(zone=zone).values(
        "name", "start_date", "end_date"
    )
    return JsonResponse(list(holidays), safe=False)


@login_required
@mediatheque_member_required
def search_workshop_titles(request):
    query = request.GET.get("title", "").strip()
    options_html = ""
    if len(query) >= 2:
        titles = (
            Workshop.objects.filter(title__icontains=query)
            .values_list("title", flat=True)
            .distinct()
            .order_by("title")[:10]
        )
        options_html = render_to_string(
            "library_workshops/partials/title_option.html",
            {"titles": titles},
            request=request,
        )
    return HttpResponse(options_html, content_type="text/html; charset=utf-8")


@login_required
@mediatheque_member_required
def edit_workshop(request, workshop_id):
    workshop = get_object_or_404(
        filter_owned(Workshop.objects.select_related("location"), request.user),
        id=workshop_id,
    )

    edit_mode = request.GET.get("mode", "single")
    pattern = workshop.recurrence_group

    if pattern and edit_mode == "all_future":
        return _edit_recurrence_pattern(request, pattern)

    if request.method == "POST":
        form = WorkshopForm(request.POST, request.FILES, instance=workshop, user=request.user)
        if form.is_valid():
            ws = form.save(commit=False)
            if pattern:
                ws.recurrence_modified = True
            ws.save()
            check_workshop_conflicts(ws, request)
            check_duplicate_title(ws, request)
            messages.success(request, "L'atelier a été modifié avec succès !")
            return redirect("library_workshops:index")
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = WorkshopForm(instance=workshop, user=request.user)

    ctx = {"form": form, "title": f"Modifier l'atelier : {workshop.title}"}
    if pattern:
        total = pattern.workshops.count()
        ctx["recurrence_info"] = {"pattern": pattern, "total": total}
    return render(request, "library_workshops/workshop_form.html", ctx)


@login_required
@mediatheque_member_required
def delete_workshop(request, workshop_id):
    workshop = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )

    if request.method == "POST":
        workshop_title = workshop.title
        workshop.delete()
        messages.success(request, f"L'atelier '{workshop_title}' a été supprimé.")
        return redirect("library_workshops:index")

    return render(
        request,
        "library_workshops/workshop_confirm_delete.html",
        {"workshop": workshop},
    )


@login_required
@mediatheque_member_required
def add_participant(request, workshop_id):
    workshop = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )

    if request.method == "POST":
        form = WorkshopParticipantForm(request.POST)
        reservation_type = request.POST.get("reservation_type", "individual")

        if form.is_valid():
            if reservation_type == "group":
                group_size = int(request.POST.get("group_size", 2))
                group_notes = request.POST.get("group_notes", "")

                with transaction.atomic():
                    participant = form.save(commit=False)
                    participant.workshop = workshop
                    participant.added_by = request.user
                    participant.is_group_leader = True
                    participant.group_size = group_size

                    if group_notes:
                        participant.notes = f"Responsable du groupe. {group_notes}"
                    else:
                        participant.notes = "Responsable du groupe"

                    if workshop.is_full:
                        participant.status = "waiting"
                        msg = (
                            f"Groupe de {group_size} personnes ajouté à la liste "
                            "d'attente car l'atelier est complet."
                        )
                        messages.warning(request, msg)
                    else:
                        participant.status = "confirmed"
                        msg = (
                            f"Groupe de {group_size} personnes ajouté avec succès "
                            "à l'atelier."
                        )
                        messages.success(request, msg)

                    participant.save()

                    timestamp = int(time.time())
                    for i in range(1, group_size):
                        WorkshopParticipant.objects.create(
                            workshop=workshop,
                            first_name=f"Membre {i}",
                            last_name=f"Groupe_{timestamp}_{participant.last_name}",
                            age=participant.age,
                            status=participant.status,
                            notes=f"Membre du groupe de {participant.full_name}",
                            added_by=request.user,
                            group_leader=participant,
                        )

                if request.headers.get("HX-Request"):
                    return JsonResponse({"success": True})
                else:
                    return redirect(
                        "library_workshops:workshop_participants",
                        workshop_id=workshop_id,
                    )
            else:
                participant = form.save(commit=False)
                participant.workshop = workshop
                participant.added_by = request.user

                if workshop.is_full:
                    participant.status = "waiting"
                    msg = (
                        f"{participant.full_name} a été ajouté à la liste "
                        "d'attente car l'atelier est complet."
                    )
                    messages.warning(request, msg)
                else:
                    participant.status = "confirmed"
                    msg = (
                        f"{participant.full_name} a été ajouté avec succès "
                        "à l'atelier."
                    )
                    messages.success(request, msg)

                participant.save()

                if request.headers.get("HX-Request"):
                    return render(
                        request,
                        "library_workshops/partials/participant_row.html",
                        {"participant": participant, "workshop": workshop},
                    )
                else:
                    return redirect(
                        "library_workshops:workshop_participants",
                        workshop_id=workshop_id,
                    )
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = WorkshopParticipantForm()

    return render(
        request,
        "library_workshops/add_participant.html",
        {
            "form": form,
            "workshop": workshop,
            "title": f"Ajouter un participant - {workshop.title}",
        },
    )


@login_required
@mediatheque_member_required
def workshop_participants(request, workshop_id):
    workshop = get_object_or_404(
        filter_owned(
            Workshop.objects.annotate(
                confirmed_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                ),
                waiting_count=Count(
                    "participants", filter=Q(participants__status="waiting")
                ),
            )
            .select_related("location")
            .prefetch_related(
                Prefetch(
                    "participants",
                    queryset=WorkshopParticipant.objects.filter(
                        status="confirmed"
                    ).select_related("group_leader", "added_by"),
                    to_attr="confirmed_participants_list",
                ),
                Prefetch(
                    "participants",
                    queryset=WorkshopParticipant.objects.filter(
                        status="waiting"
                    ).select_related("group_leader", "added_by"),
                    to_attr="waiting_participants_list",
                ),
            ),
            request.user,
        ),
        id=workshop_id,
    )

    workshop._confirmed_prefetched = True
    workshop._waiting_prefetched = True

    return render(
        request,
        "library_workshops/workshop_participants.html",
        {"workshop": workshop, "title": f"Participants - {workshop.title}"},
    )


@login_required
@mediatheque_member_required
def add_group_reservation(request, workshop_id):
    workshop = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )

    if request.method == "POST":
        form = WorkshopGroupReservationForm(request.POST, workshop=workshop)
        if form.is_valid():
            with transaction.atomic():
                leader = WorkshopParticipant.objects.create(
                    workshop=workshop,
                    first_name=form.cleaned_data["leader_first_name"],
                    last_name=form.cleaned_data["leader_last_name"],
                    age=form.cleaned_data["leader_age"],
                    email=form.cleaned_data["leader_email"],
                    phone=form.cleaned_data["leader_phone"],
                    status=form.cleaned_data["status"],
                    notes=form.cleaned_data["additional_notes"],
                    added_by=request.user,
                    is_group_leader=True,
                    group_size=form.cleaned_data["group_size"],
                )

                group_size = form.cleaned_data["group_size"]
                for i in range(1, group_size):
                    WorkshopParticipant.objects.create(
                        workshop=workshop,
                        first_name=f"Membre {i}",
                        last_name=f"du groupe de {leader.full_name}",
                        age=leader.age,
                        status=form.cleaned_data["status"],
                        notes=f"Membre du groupe de {leader.full_name}",
                        added_by=request.user,
                        group_leader=leader,
                    )

                if group_size == 2:
                    msg = (
                        f"Réservation de groupe créée : {leader.full_name} "
                        "et 1 autre personne"
                    )
                else:
                    msg = (
                        f"Réservation de groupe créée : {leader.full_name} "
                        f"et {group_size - 1} autres personnes"
                    )

                if form.cleaned_data["status"] == "waiting":
                    msg += " (ajouté à la liste d'attente)"

                messages.success(request, msg)

                if request.headers.get("HX-Request"):
                    return JsonResponse({"success": True})
                else:
                    return redirect(
                        "library_workshops:workshop_participants",
                        workshop_id=workshop_id,
                    )
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = WorkshopGroupReservationForm(workshop=workshop)

    return render(
        request,
        "library_workshops/add_group_reservation.html",
        {
            "form": form,
            "workshop": workshop,
            "title": f"Réservation de groupe - {workshop.title}",
        },
    )


@login_required
@require_POST
def remove_participant(request, workshop_id, participant_id):
    if not (
        request.user.groups.filter(name="mediatheque").exists()
        or request.user.is_superuser
    ):
        return JsonResponse({"error": "Accès refusé"}, status=403)

    try:
        workshop = get_object_or_404(
            filter_owned(Workshop.objects.all(), request.user), id=workshop_id
        )
        participant = get_object_or_404(
            WorkshopParticipant, id=participant_id, workshop=workshop
        )
        participant_name = participant.full_name

        if participant.is_group_leader:
            group_members_count = WorkshopParticipant.objects.filter(
                group_leader=participant
            ).count()

            if group_members_count > 0:
                return JsonResponse(
                    {
                        "error": "group_leader_with_members",
                        "message": f'Le responsable du groupe "{participant_name}" a {group_members_count} membre(s). Voulez-vous supprimer tout le groupe ?',
                        "group_members_count": group_members_count,
                    },
                    status=400,
                )
            else:
                participant.delete()
                messages.success(
                    request, f"{participant_name} a été retiré de l'atelier."
                )

        elif participant.group_leader:
            participant.delete()
            messages.success(request, f"{participant_name} a été retiré de l'atelier.")

            leader = participant.group_leader
            remaining_members = WorkshopParticipant.objects.filter(
                group_leader=leader
            ).count()
            leader.group_size = remaining_members + 1
            leader.save()

        else:
            participant.delete()
            messages.success(request, f"{participant_name} a été retiré de l'atelier.")

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_POST
def move_to_waiting_list(request, workshop_id, participant_id):
    if not (
        request.user.groups.filter(name="mediatheque").exists()
        or request.user.is_superuser
    ):
        return JsonResponse({"error": "Accès refusé"}, status=403)

    workshop = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )
    participant = get_object_or_404(
        WorkshopParticipant, id=participant_id, workshop=workshop
    )
    try:
        participant.status = "waiting"
        participant.save()

        messages.info(
            request, f"{participant.full_name} a été déplacé vers la liste d'attente."
        )

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_POST
def move_from_waiting_list(request, workshop_id, participant_id):
    if not (
        request.user.groups.filter(name="mediatheque").exists()
        or request.user.is_superuser
    ):
        return JsonResponse({"error": "Accès refusé"}, status=403)

    workshop = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )
    participant = get_object_or_404(
        WorkshopParticipant, id=participant_id, workshop=workshop
    )

    is_overbooked = workshop.is_full

    participant.status = "confirmed"
    participant.save()

    if is_overbooked:
        messages.warning(
            request,
            f"{participant.full_name} a été confirmé. L'atelier dépasse maintenant sa capacité ({workshop.current_participants_count}/{workshop.max_participants} participants).",
        )
    else:
        messages.success(
            request, f"{participant.full_name} a été confirmé pour l'atelier."
        )

    if (
        request.headers.get("HX-Request")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):
        return JsonResponse({"success": True, "overbooked": is_overbooked})
    else:
        return redirect(
            "library_workshops:workshop_participants", workshop_id=workshop_id
        )


@login_required
@require_POST
def remove_group(request, workshop_id, participant_id):
    if not (
        request.user.groups.filter(name="mediatheque").exists()
        or request.user.is_superuser
    ):
        return JsonResponse({"error": "Accès refusé"}, status=403)

    workshop = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )
    participant = get_object_or_404(
        WorkshopParticipant, id=participant_id, workshop=workshop
    )

    try:
        if not participant.is_group_leader:
            return JsonResponse(
                {"error": "Ce participant n'est pas responsable de groupe"}, status=400
            )

        participant_name = participant.full_name

        group_members = WorkshopParticipant.objects.filter(group_leader=participant)
        group_members_count = group_members.count()
        group_members.delete()

        participant.delete()

        messages.success(
            request,
            f"Groupe de {participant_name} ({group_members_count + 1} personne(s)) supprimé avec succès.",
        )

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@mediatheque_member_required
def workshop_detail(request, workshop_id):
    workshop = get_object_or_404(
        filter_owned(
            Workshop.objects.select_related("location").prefetch_related(
                Prefetch(
                    "participants",
                    queryset=WorkshopParticipant.objects.filter(
                        status="confirmed"
                    ).select_related("group_leader", "added_by"),
                    to_attr="confirmed_participants_list",
                ),
                Prefetch(
                    "participants",
                    queryset=WorkshopParticipant.objects.filter(
                        status="waiting"
                    ).select_related("group_leader", "added_by"),
                    to_attr="waiting_participants_list",
                ),
            ),
            request.user,
        ),
        id=workshop_id,
    )

    workshop._confirmed_prefetched = True
    workshop._waiting_prefetched = True

    return render(
        request,
        "library_workshops/workshop_detail.html",
        {"workshop": workshop, "title": f"Détails - {workshop.title}"},
    )


def access_denied(request):
    return render(request, "library_workshops/access_denied.html", status=403)


@login_required
@mediatheque_member_required
def workshop_statistics(request):
    period = request.GET.get("period", "12_months")
    end_date = timezone.now().date()

    start_date, end_date = WorkshopStatisticsService.get_period_dates_static(period)
    service = WorkshopStatisticsService(
        start_date=start_date, end_date=end_date, user=request.user
    )

    stats = service.get_all_statistics()

    monthly_data = []
    for item in stats.get("monthly_data", []):
        try:
            month_str = None
            if item.get("month"):
                if hasattr(item["month"], "strftime"):
                    month_str = item["month"].strftime("%Y-%m-%d")
                else:
                    month_str = str(item["month"])

            monthly_data.append(
                {
                    "month": month_str,
                    "workshop_count": int(item.get("workshop_count", 0)),
                    "participant_count": int(item.get("participant_count", 0)),
                }
            )
        except (KeyError, AttributeError, ValueError) as e:
            logger.warning("Erreur traitement données mensuelles: %s", e)
            continue

    yearly_data = []
    for item in stats.get("yearly_data", []):
        try:
            yearly_data.append(
                {
                    "year": int(item.get("year", 0)),
                    "workshop_count": int(item.get("workshop_count", 0)),
                    "participant_count": int(item.get("participant_count", 0)),
                }
            )
        except (KeyError, ValueError) as e:
            logger.warning("Erreur traitement données annuelles: %s", e)
            continue

    logger.debug(
        "Période: %s | Date début: %s | Date fin: %s", period, start_date, end_date
    )
    logger.debug("Données mensuelles préparées: %s", monthly_data)
    logger.debug("Données annuelles préparées: %s", yearly_data)
    logger.debug("Répartition par âge: %s", stats.get("age_distribution", {}))

    context = {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "title": "Statistiques des ateliers",
        **stats,
        "monthly_data": monthly_data,
        "yearly_data": yearly_data,
        "age_distribution": stats.get("age_distribution", {}),
    }

    return render(request, "library_workshops/statistics.html", context)


@login_required
@mediatheque_member_required
def workshop_archives(request):
    years = list(
        filter_owned(
            Workshop.objects.annotate(year=ExtractYear("start_date")), request.user
        )
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )

    selected_year = request.GET.get("year")
    if selected_year:
        selected_year = int(selected_year)
    else:
        selected_year = years[0] if years else timezone.now().year

    workshops_by_year = {}
    year_stats = {}

    if years:
        all_workshops = list(
            filter_owned(
                Workshop.objects.annotate(year=ExtractYear("start_date"))
                .annotate(
                    confirmed_count=Count(
                        "participants", filter=Q(participants__status="confirmed")
                    ),
                    waiting_count=Count(
                        "participants", filter=Q(participants__status="waiting")
                    ),
                )
                .select_related("location"),
                request.user,
            ).order_by("start_date", "start_time")
        )

        for workshop in all_workshops:
            workshop.participant_count = workshop.confirmed_count
            workshop.fill_rate = (
                (workshop.confirmed_count / workshop.max_participants * 100)
                if workshop.max_participants > 0
                else 0
            )

        grouped = {}
        for w in all_workshops:
            y = getattr(w, "year", None)
            if y is None:
                y = w.start_date.year
            grouped.setdefault(y, []).append(w)

        for year in years:
            ws = grouped.get(year, [])
            workshops_by_year[year] = ws
            total_workshops = len(ws)
            total_participants = sum(w.confirmed_count for w in ws)
            total_capacity = sum(w.max_participants for w in ws)
            avg_fill_rate = (
                (total_participants / total_capacity * 100) if total_capacity > 0 else 0
            )

            year_stats[year] = {
                "total_workshops": total_workshops,
                "total_participants": total_participants,
                "total_capacity": total_capacity,
                "avg_fill_rate": round(avg_fill_rate, 1),
                "avg_participants_per_workshop": (
                    round(total_participants / total_workshops, 1)
                    if total_workshops > 0
                    else 0
                ),
                "workshops": ws,
            }

    context = {
        "years": years,
        "selected_year": selected_year,
        "workshops_by_year": workshops_by_year,
        "year_stats": year_stats,
        "title": "Archives des ateliers",
    }

    return render(request, "library_workshops/archives.html", context)


@login_required
@mediatheque_member_required
def create_location_modal(request):
    """Vue HTMX : retourne le fragment HTML du modal de création de lieu"""
    form = QuickLocationForm()
    qs = VisitorLocation.objects.filter(is_active=True)
    if not request.user.is_superuser:
        qs = qs.filter(user=request.user)
    existing_locations = qs.order_by("order", "name")
    html = render_to_string(
        "library_workshops/partials/location_modal.html",
        {
            "form": form,
            "existing_locations": existing_locations,
        },
        request=request,
    )
    return HttpResponse(html)


@login_required
@mediatheque_member_required_json
def create_location(request):
    """Vue HTMX : crée un lieu et retourne l'option à insérer dans le select"""
    if request.method == "POST":
        form = QuickLocationForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            icon = form.cleaned_data["icon"]
            color = form.cleaned_data["color"]

            if (
                filter_location_owned(VisitorLocation.objects.all(), request.user)
                .filter(name__iexact=name)
                .exists()
            ):
                return JsonResponse(
                    {"error": f'Un lieu nommé "{name}" existe déjà.'}, status=400
                )

            max_order = (
                filter_location_owned(
                    VisitorLocation.objects.all(), request.user
                ).aggregate(m=Max("order"))["m"]
                or 0
            )

            location = VisitorLocation.objects.create(
                name=name,
                icon=icon,
                color=color,
                user=request.user,
                is_active=True,
                order=max_order + 1,
            )

            option_html = render_to_string(
                "library_workshops/partials/location_option.html",
                {"location": location},
                request=request,
            )

            return JsonResponse(
                {
                    "success": True,
                    "option_html": option_html,
                    "location_id": location.id,
                    "location_name": location.name,
                }
            )
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = [str(e) for e in field_errors]
            return JsonResponse(
                {"error": "Formulaire invalide", "errors": errors}, status=400
            )

    return JsonResponse({"error": "Méthode non autorisée"}, status=405)


@login_required
@mediatheque_member_required
def workshop_calendar(request):
    """Vue pour afficher le calendrier des ateliers"""
    return render(
        request,
        "library_workshops/workshop_calendar.html",
        {"title": "Calendrier des ateliers"},
    )


@login_required
@mediatheque_member_required
def workshop_calendar_events(request):
    """Endpoint JSON pour FullCalendar"""
    from django.utils.dateparse import parse_date

    start_str = request.GET.get("start")
    end_str = request.GET.get("end")

    workshops = filter_owned(
        Workshop.objects.all()
        .select_related("location")
        .annotate(
            confirmed_count=Count(
                "participants", filter=Q(participants__status="confirmed")
            ),
            waiting_count=Count(
                "participants", filter=Q(participants__status="waiting")
            ),
        ),
        request.user,
    )

    if start_str:
        start_date = parse_date(start_str[:10])
        if start_date:
            workshops = workshops.filter(
                Q(end_date__gte=start_date)
                | Q(end_date__isnull=True, start_date__gte=start_date)
            )
    if end_str:
        end_date = parse_date(end_str[:10])
        if end_date:
            workshops = workshops.filter(start_date__lte=end_date)

    events = []
    for w in workshops:
        end_date = w.end_date if w.end_date else w.start_date
        color = w.location.color if w.location else "#4a6fa5"
        text_color = "#ffffff"

        events.append(
            {
                "id": str(w.id),
                "title": w.title,
                "start": f"{w.start_date.isoformat()}T{w.start_time.isoformat()}",
                "end": f"{end_date.isoformat()}T{w.end_time.isoformat()}",
                "color": color,
                "textColor": text_color,
                "url": reverse("library_workshops:workshop_detail", args=[w.id]),
                "extendedProps": {
                    "location": w.location.name if w.location else "Non défini",
                    "age_range": w.age_range_display,
                    "confirmed": w.confirmed_count,
                    "waiting": w.waiting_count,
                    "capacity": w.max_participants,
                },
            }
        )

    return JsonResponse(events, safe=False)


@login_required
@mediatheque_member_required
@require_POST
def duplicate_workshop(request, workshop_id):
    """Duplique un atelier avec ses données (sans les participants)"""
    original = get_object_or_404(
        filter_owned(Workshop.objects.all(), request.user), id=workshop_id
    )
    clone = Workshop.objects.get(pk=original.pk)
    clone.pk = None
    clone.title = f"{original.title} (Copie)"
    clone.created_by = request.user
    clone.reminder_sent = False
    clone.save()

    messages.success(
        request, f"L'atelier '{original.title}' a été dupliqué avec succès !"
    )
    return redirect("library_workshops:edit_workshop", workshop_id=clone.id)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def newsletter_view(request):
    data = NewsletterService.get_newsletter_data()
    return render(request, "library_workshops/newsletter.html", data)
