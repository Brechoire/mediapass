import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User

from library_workshops.decorators import (
    mediatheque_member_required,
    mediatheque_member_required_json,
)
from library_workshops.utils import filter_owned, filter_location_owned
from .models import Closure, Location, VisitorCount
from .opening import (
    DEFAULT_OPENING_WEEKDAYS,
    WEEKDAY_LABELS,
    build_closure_map,
    get_closures,
    get_open_dates,
    get_opening_weekdays,
    group_dates_into_ranges,
)
from accounts.models import LibraryProfile
from .forms import BulkVisitorCountForm, DateRangeForm, LocationForm
from .services import SuperadminStatisticsService
from .reporting import AnnualReportService
from .docx_report import build_annual_report_docx

# Constantes partagées entre les vues d'espaces
SPACE_ICONS = [
    ("bx-building", "Bâtiment"),
    ("bx-book", "Livre"),
    ("bx-book-reader", "Lecteur"),
    ("bx-library", "Bibliothèque"),
    ("bx-game", "Jeu"),
    ("bx-joystick", "Joystick"),
    ("bx-music", "Musique"),
    ("bx-movie", "Film"),
    ("bx-desktop", "Ordinateur"),
    ("bx-laptop", "Portable"),
    ("bx-user", "Utilisateur"),
    ("bx-group", "Groupe"),
    ("bx-child", "Enfant"),
    ("bx-home", "Maison"),
    ("bx-store", "Magasin"),
    ("bx-coffee", "Café"),
]

SPACE_COLORS = [
    ("#4F46E5", "Indigo"),
    ("#7C3AED", "Violet"),
    ("#EC4899", "Rose"),
    ("#EF4444", "Rouge"),
    ("#F97316", "Orange"),
    ("#EAB308", "Jaune"),
    ("#22C55E", "Vert"),
    ("#14B8A6", "Turquoise"),
    ("#06B6D4", "Cyan"),
    ("#3B82F6", "Bleu"),
    ("#6366F1", "Indigo clair"),
    ("#8B5CF6", "Violet clair"),
]


def _resolve_index_scope(request):
    """Médiathèque affichée sur la page de pointage.

    Un membre voit sa médiathèque. Un superadmin choisit une médiathèque via
    ``?commune=`` ; à défaut, on prend la sienne ou la première disponible.
    """
    if not request.user.is_superuser:
        return request.user, "", []

    available = AnnualReportService.get_available_communes()
    commune = (
        request.GET.get("commune")
        or request.POST.get("commune")
        or ""
    ).strip()
    scope_user = next(
        (user for user in available if user.username == commune),
        None,
    )
    if scope_user is None:
        if request.user.locations.exists():
            scope_user = request.user
        elif available:
            scope_user = available[0]

    if scope_user is None:
        return None, "", available
    return scope_user, scope_user.username, available


@mediatheque_member_required
def index(request):
    """Dashboard principal avec compteurs temps réel."""
    today = timezone.now().date()
    scope_user, commune, available_communes = _resolve_index_scope(request)

    locations = Location.objects.none()
    if scope_user is not None:
        locations = Location.objects.filter(
            is_active=True, user=scope_user
        ).order_by("order", "name")
    location_ids = list(locations.values_list("id", flat=True))

    today_counts = (
        VisitorCount.objects.filter(
            location__user=scope_user, date=today
        ).select_related("updated_by")
        if scope_user is not None
        else VisitorCount.objects.none()
    )
    today_map = {entry.location_id: entry for entry in today_counts}

    week_start = today - timedelta(days=6)
    month_start = today.replace(day=1)
    last_7_days = (
        VisitorCount.objects.filter(
            location__user=scope_user,
            date__gte=week_start,
            date__lte=today,
        )
        .values("location_id", "date")
        .annotate(total=Sum("count"))
        .order_by("date")
        if scope_user is not None
        else []
    )
    daily_by_location = {}
    for entry in last_7_days:
        daily_by_location.setdefault(entry["location_id"], {})[
            entry["date"]
        ] = entry["total"]

    opening_weekdays = (
        get_opening_weekdays(scope_user)
        if scope_user is not None
        else list(DEFAULT_OPENING_WEEKDAYS)
    )
    today_closure_map = (
        build_closure_map(scope_user, today, today)
        if scope_user is not None
        else {}
    )
    today_closure = today_closure_map.get(today)
    today_is_closed = (
        scope_user is not None
        and (
            today_closure is not None
            or today.weekday() not in opening_weekdays
        )
    )

    location_data = []
    for location in locations:
        count_obj = today_map.get(location.id)
        sparkline = []
        sparkline_labels = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            sparkline.append(
                daily_by_location.get(location.id, {}).get(day, 0)
            )
            sparkline_labels.append(day.strftime("%d/%m"))
        location_data.append(
            {
                "location": location,
                "count": count_obj.count if count_obj else 0,
                "count_id": count_obj.id if count_obj else None,
                "has_pointage": count_obj is not None,
                "is_zero": (
                    count_obj is not None and count_obj.count == 0
                ),
                "updated_at": (
                    count_obj.updated_at if count_obj else None
                ),
                "updated_by": (
                    count_obj.updated_by if count_obj else None
                ),
                "sparkline": sparkline,
                "sparkline_labels": sparkline_labels,
                "workshops": [],
            }
        )

    total_today = sum(item["count"] for item in location_data)
    spaces_total = len(location_data)
    spaces_pointed = sum(
        1 for item in location_data if item["has_pointage"]
    )
    spaces_missing = [
        item for item in location_data if not item["has_pointage"]
    ]
    all_pointed = spaces_total > 0 and not spaces_missing
    last_update = max(
        (
            item["updated_at"]
            for item in location_data
            if item["updated_at"] is not None
        ),
        default=None,
    )

    # Ateliers de la médiathèque aujourd'hui (compteurs agrégés uniquement).
    if location_ids:
        from library_workshops.models import Workshop

        today_workshops = (
            Workshop.objects.filter(
                location_id__in=location_ids,
                status__in=["active", "cancelled"],
            )
            .filter(
                Q(start_date=today)
                | Q(start_date__lt=today, end_date__gte=today)
            )
            .select_related("location")
            .annotate(
                confirmed_count=Count(
                    "participants",
                    filter=Q(participants__status="confirmed"),
                )
            )
            .order_by("start_time")
        )
        workshops_by_location = {}
        for workshop in today_workshops:
            workshops_by_location.setdefault(
                workshop.location_id, []
            ).append(workshop)
        for item in location_data:
            item["workshops"] = workshops_by_location.get(
                item["location"].id, []
            )

    def period_stats(start_date):
        closure_map = (
            build_closure_map(scope_user, start_date, today)
            if scope_user is not None
            else {}
        )
        open_dates = (
            get_open_dates(
                start_date,
                today,
                opening_weekdays,
                closure_map,
            )
            if scope_user is not None
            else set()
        )
        open_total = 0
        exceptional_total = 0
        if scope_user is not None:
            open_total = (
                VisitorCount.objects.filter(
                    location__user=scope_user,
                    date__in=open_dates,
                ).aggregate(total=Sum("count"))["total"]
                or 0
            )
            exceptional_total = (
                VisitorCount.objects.filter(
                    location__user=scope_user,
                    date__gte=start_date,
                    date__lte=today,
                )
                .exclude(date__in=open_dates)
                .aggregate(total=Sum("count"))["total"]
                or 0
            )
        open_days = len(open_dates)
        closure_days = sum(
            1
            for day in closure_map
            if day.weekday() in opening_weekdays
        )
        return {
            "total": open_total + exceptional_total,
            "open_total": open_total,
            "open_days": open_days,
            "closure_days": closure_days,
            "exceptional_total": exceptional_total,
            "avg": round(open_total / open_days, 1) if open_days else 0,
        }

    week_stats = period_stats(week_start)
    month_stats = period_stats(month_start)

    # Comparaison avec le même jour de la semaine précédente.
    last_week_day = today - timedelta(days=7)
    last_week_closure_map = (
        build_closure_map(scope_user, last_week_day, last_week_day)
        if scope_user is not None
        else {}
    )
    last_week_open = (
        scope_user is not None
        and last_week_day.weekday() in opening_weekdays
        and last_week_day not in last_week_closure_map
    )
    last_week_total = None
    today_variation = None
    if last_week_open and not today_is_closed:
        last_week_total = (
            VisitorCount.objects.filter(
                location__user=scope_user, date=last_week_day
            ).aggregate(total=Sum("count"))["total"]
            or 0
        )
        if last_week_total > 0:
            today_variation = round(
                (total_today - last_week_total)
                / last_week_total
                * 100,
                1,
            )

    # Prochaine fermeture / prochaine réouverture.
    next_closure = None
    next_open_date = None
    if scope_user is not None:
        next_closure = (
            Closure.objects.filter(
                user=scope_user, start_date__gt=today
            )
            .order_by("start_date", "end_date")
            .first()
        )
        if today_is_closed:
            horizon = today + timedelta(days=366)
            horizon_map = build_closure_map(
                scope_user, today, horizon
            )
            cursor = today + timedelta(days=1)
            while cursor <= horizon:
                if (
                    cursor.weekday() in opening_weekdays
                    and cursor not in horizon_map
                ):
                    next_open_date = cursor
                    break
                cursor += timedelta(days=1)

    context = {
        "location_data": location_data,
        "today": today,
        "total_today": total_today,
        "week_total": week_stats["total"],
        "month_total": month_stats["total"],
        "week_stats": week_stats,
        "month_stats": month_stats,
        "spaces_total": spaces_total,
        "spaces_pointed": spaces_pointed,
        "spaces_missing": spaces_missing,
        "all_pointed": all_pointed,
        "last_update": last_update,
        "today_closure": today_closure,
        "today_is_closed": today_is_closed,
        "next_closure": next_closure,
        "next_open_date": next_open_date,
        "today_variation": today_variation,
        "commune": commune,
        "available_communes": available_communes,
        "can_manage_spaces": (
            scope_user is not None and scope_user == request.user
        ),
        "title": "Pointage visiteurs",
    }

    return render(request, "visitor_tracking/index.html", context)


@mediatheque_member_required_json
@require_POST
def increment_count(request, location_id, amount=1):
    """Incrémenter le compteur d'un espace (+N visiteurs)."""
    today = timezone.now().date()
    location = get_object_or_404(
        filter_location_owned(
            Location.objects.filter(
                is_active=True, user__isnull=False
            ),
            request.user,
        ),
        id=location_id,
    )

    amount = max(1, min(int(amount), 99))
    owner = location.user
    opening_weekdays = get_opening_weekdays(owner)
    closure_map = build_closure_map(owner, today, today)
    if (
        today.weekday() not in opening_weekdays
        or today in closure_map
    ):
        return JsonResponse(
            {
                "success": False,
                "closed": True,
                "error": (
                    "La médiathèque est fermée aujourd'hui. "
                    "Utilisez la saisie rétroactive pour une ouverture "
                    "exceptionnelle."
                ),
            },
            status=409,
        )

    with transaction.atomic():
        count_obj, created = (
            VisitorCount.objects.select_for_update().get_or_create(
                location=location,
                date=today,
                defaults={
                    "count": amount,
                    "created_by": request.user,
                    "updated_by": request.user,
                },
            )
        )
        if not created:
            VisitorCount.objects.filter(pk=count_obj.pk).update(
                count=F("count") + amount,
                updated_by=request.user,
                updated_at=timezone.now(),
            )
            count_obj.refresh_from_db()

    total_today = (
        VisitorCount.objects.filter(
            location__user=owner,
            location__is_active=True,
            date=today,
        ).aggregate(total=Sum("count"))["total"]
        or 0
    )

    return JsonResponse(
        {
            "success": True,
            "count": count_obj.count,
            "total_today": total_today,
        }
    )


@mediatheque_member_required_json
@require_POST
def decrement_count(request, location_id):
    """Décrémenter le compteur d'un espace (-1), sans créer de ligne."""
    today = timezone.now().date()
    location = get_object_or_404(
        filter_location_owned(
            Location.objects.filter(
                is_active=True, user__isnull=False
            ),
            request.user,
        ),
        id=location_id,
    )
    owner = location.user

    changed = False
    count_obj = VisitorCount.objects.filter(
        location=location, date=today
    ).first()
    if count_obj is not None and count_obj.count > 0:
        changed = (
            VisitorCount.objects.filter(
                pk=count_obj.pk, count__gt=0
            ).update(
                count=F("count") - 1,
                updated_by=request.user,
                updated_at=timezone.now(),
            )
            > 0
        )
        count_obj.refresh_from_db()

    total_today = (
        VisitorCount.objects.filter(
            location__user=owner,
            location__is_active=True,
            date=today,
        ).aggregate(total=Sum("count"))["total"]
        or 0
    )

    return JsonResponse(
        {
            "success": True,
            "changed": changed,
            "count": count_obj.count if count_obj else 0,
            "total_today": total_today,
        }
    )


@mediatheque_member_required
def entry_form(request):
    """Formulaire de saisie rétroactive (par date)."""
    scope_user, commune, available_communes = _resolve_index_scope(request)
    if scope_user is None:
        messages.error(request, "Aucune médiathèque disponible.")
        return redirect("visitor_tracking:index")

    if request.method == "POST" and request.user.is_superuser:
        requested_commune = (
            request.POST.get("commune") or ""
        ).strip()
        if requested_commune and requested_commune != commune:
            messages.error(
                request,
                "La médiathèque sélectionnée n'existe plus. "
                "Aucune donnée n'a été enregistrée.",
            )
            return redirect("visitor_tracking:index")

    selected_date = None
    selected_closure = None
    selected_is_closed = False
    opening_weekdays = get_opening_weekdays(scope_user)
    first_calendar_year = getattr(
        settings, "VISITOR_REPORT_V2_FROM_YEAR", 2026
    )

    if request.method == "POST":
        form = BulkVisitorCountForm(request.POST, user=scope_user)
        if form.is_valid():
            date = form.cleaned_data["date"]
            selected_date = date
            if date.year >= first_calendar_year:
                closure_map = build_closure_map(
                    scope_user, date, date
                )
                selected_closure = closure_map.get(date)
                selected_is_closed = (
                    selected_closure is not None
                    or date.weekday() not in opening_weekdays
                )
            if selected_is_closed and not form.cleaned_data.get(
                "confirm_closed"
            ):
                form.add_error(
                    None,
                    "Ce jour est un jour de fermeture. Cochez la "
                    "confirmation pour enregistrer une ouverture "
                    "exceptionnelle.",
                )
            else:
                active_locations = Location.objects.filter(
                    is_active=True, user=scope_user
                )

                submitted_ids = {
                    int(key.removeprefix("location_"))
                    for key in form.cleaned_data
                    if key.startswith("location_")
                }
                active_ids = set(
                    active_locations.values_list("id", flat=True)
                )
                missing_ids = submitted_ids - active_ids
                if missing_ids:
                    missing_names = list(
                        Location.objects.filter(
                            id__in=missing_ids
                        ).values_list("name", flat=True)
                    )
                    if missing_names:
                        messages.warning(
                            request,
                            "Espaces ignorés car désactivés depuis "
                            "l'ouverture du formulaire : "
                            f"{', '.join(missing_names)}.",
                        )

                saved_count = 0
                for location in active_locations:
                    field_name = f"location_{location.id}"
                    count = form.cleaned_data.get(field_name, 0) or 0

                    count_obj, created = (
                        VisitorCount.objects.get_or_create(
                            location=location,
                            date=date,
                            defaults={
                                "count": count,
                                "created_by": request.user,
                                "updated_by": request.user,
                            },
                        )
                    )
                    if not created and count_obj.count != count:
                        count_obj.count = count
                        count_obj.updated_by = request.user
                        count_obj.save()
                    saved_count += 1

                messages.success(
                    request,
                    f"Comptages enregistrés pour le "
                    f"{date.strftime('%d/%m/%Y')} "
                    f"({saved_count} espaces).",
                )
                target = reverse("visitor_tracking:index")
                if commune:
                    target = f"{target}?commune={commune}"
                return redirect(target)
    else:
        initial_date = request.GET.get("date")
        form_initial = {}

        if initial_date:
            try:
                date_obj = datetime.strptime(
                    initial_date, "%Y-%m-%d"
                ).date()
                form_initial["date"] = date_obj
                selected_date = date_obj
                if date_obj.year >= first_calendar_year:
                    closure_map = build_closure_map(
                        scope_user, date_obj, date_obj
                    )
                    selected_closure = closure_map.get(date_obj)
                    selected_is_closed = (
                        selected_closure is not None
                        or date_obj.weekday() not in opening_weekdays
                    )

                existing_counts = VisitorCount.objects.filter(
                    location__user=scope_user,
                    date=date_obj,
                ).select_related("location")
                for count in existing_counts:
                    field_name = f"location_{count.location.id}"
                    form_initial[field_name] = count.count
            except (ValueError, TypeError):
                pass

        form = BulkVisitorCountForm(
            user=scope_user, initial=form_initial
        )

    context = {
        "form": form,
        "location_fields": form.get_location_fields(user=scope_user),
        "selected_date": selected_date,
        "selected_closure": selected_closure,
        "selected_is_closed": selected_is_closed,
        "commune": commune,
        "available_communes": available_communes,
        "can_manage_spaces": scope_user == request.user,
        "title": "Saisie des visiteurs",
    }

    return render(request, "visitor_tracking/entry_form.html", context)


@mediatheque_member_required
def statistics(request):
    """Page des statistiques avec graphiques"""
    form = DateRangeForm(request.GET or None)

    # Déterminer la période
    period = request.GET.get("period", "30_days")
    location_id = request.GET.get("location")

    today = timezone.now().date()

    # Calculer les dates selon la période
    if period == "7_days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == "30_days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == "this_month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "last_month":
        first_of_month = today.replace(day=1)
        end_date = first_of_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif period == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif period == "custom":
        sd = request.GET.get("start_date")
        ed = request.GET.get("end_date")
        if sd and ed:
            try:
                start_date = datetime.strptime(sd, "%Y-%m-%d").date()
                end_date = datetime.strptime(ed, "%Y-%m-%d").date()
            except ValueError:
                start_date = today - timedelta(days=30)
                end_date = today
        else:
            start_date = today - timedelta(days=30)
            end_date = today
    else:
        start_date = today - timedelta(days=30)
        end_date = today

    period_length = (end_date - start_date).days or 1

    # Requête de base
    qs = filter_owned(
        VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date),
        request.user,
        field="location__user",
    )

    # Période précédente
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date - timedelta(days=1)
    prev_qs = filter_owned(
        VisitorCount.objects.filter(date__gte=prev_start, date__lte=prev_end),
        request.user,
        field="location__user",
    )

    # Filtrer par espace
    selected_location = None
    if location_id:
        try:
            selected_location = filter_location_owned(
                Location.objects.all(), request.user
            ).get(id=location_id)
            qs = qs.filter(location=selected_location)
            prev_qs = prev_qs.filter(location=selected_location)
        except Location.DoesNotExist:
            pass

    qs_no_sunday = qs.exclude(date__week_day=1)
    prev_qs_no_sunday = prev_qs.exclude(date__week_day=1)

    opening_weekdays = get_opening_weekdays(request.user)
    closure_map = build_closure_map(request.user, start_date, end_date)
    first_v2 = date(
        getattr(settings, "VISITOR_REPORT_V2_FROM_YEAR", 2026), 1, 1
    )
    closure_aware = end_date >= first_v2
    if closure_aware:
        effective_start = max(start_date, first_v2)
        open_dates = get_open_dates(
            effective_start, end_date, opening_weekdays, closure_map
        )
        if start_date < effective_start:
            cursor = start_date
            while cursor < effective_start:
                if cursor.weekday() != 6:
                    open_dates.add(cursor)
                cursor += timedelta(days=1)
        open_days = len(open_dates)
        closure_days = sum(
            1
            for day in closure_map
            if day >= first_v2
            and day.weekday() in opening_weekdays
        )
        stats_qs = qs.filter(date__in=open_dates)
        exceptional_total = (
            qs.exclude(date__in=open_dates).aggregate(total=Sum("count"))[
                "total"
            ]
            or 0
        )
    else:
        open_dates = None
        open_days = period_length
        closure_days = 0
        stats_qs = qs_no_sunday
        exceptional_total = 0

    # Stats globales sur les jours d'ouverture
    stats = stats_qs.aggregate(
        total=Sum("count"),
        days_count=Count("date", distinct=True),
        max_count=Max("count"),
    )
    open_total = stats["total"] or 0
    total_visitors = open_total + exceptional_total
    days_with_data = stats["days_count"] or 0
    avg_per_day = (
        round(open_total / open_days, 1) if open_days > 0 else 0
    )
    missing_days = (
        max(open_days - days_with_data, 0)
        if closure_aware
        else None
    )
    completeness = (
        round(days_with_data / open_days * 100, 1)
        if closure_aware and open_days
        else None
    )

    # Meilleur et pire jour
    daily_totals = (
        stats_qs.values("date")
        .annotate(total=Sum("count"))
        .order_by("-total")
    )
    best_day = daily_totals.first()
    worst_day = daily_totals.order_by("total").first()

    # Record
    record_day = best_day  # best_day is already the max total

    # Moyenne par jour de semaine / jour d'ouverture
    weekday_data = (
        stats_qs.values("date")
        .annotate(total=Sum("count"))
        .order_by("date")
    )
    weekday_sums = {}
    weekday_counts = {}
    for d in weekday_data:
        wd = d["date"].weekday()
        weekday_sums[wd] = weekday_sums.get(wd, 0) + d["total"]
        weekday_counts[wd] = weekday_counts.get(wd, 0) + 1

    weekday_days = (
        opening_weekdays if closure_aware else [0, 1, 2, 3, 4, 5]
    )
    weekday_avg_list = []
    max_wavg = 0
    for day in weekday_days:
        val = (
            weekday_sums.get(day, 0) / weekday_counts.get(day, 1)
            if weekday_counts.get(day, 0) > 0
            else 0
        )
        val = round(val, 1)
        weekday_avg_list.append(
            {"name": WEEKDAY_LABELS[day], "avg": val}
        )
        if val > max_wavg:
            max_wavg = val

    # Meilleur et pire jour de la semaine
    sorted_days = sorted(
        weekday_avg_list, key=lambda x: x["avg"], reverse=True
    )
    best_weekday = sorted_days[0] if sorted_days else None
    worst_weekday = sorted_days[-1] if sorted_days else None

    # Semaine vs week-end (samedi seulement, si ouvert)
    weekdays_total = sum(
        weekday_sums.get(day, 0)
        for day in weekday_days
        if day < 5
    )
    weekend_total = (
        weekday_sums.get(5, 0) if 5 in weekday_days else 0
    )
    weekdays_count = sum(
        weekday_counts.get(day, 0)
        for day in weekday_days
        if day < 5
    )
    weekend_count = (
        weekday_counts.get(5, 0) if 5 in weekday_days else 0
    )
    weekday_avg = (
        round(weekdays_total / weekdays_count, 1)
        if weekdays_count > 0
        else 0
    )
    weekend_avg = (
        round(weekend_total / weekend_count, 1)
        if weekend_count > 0
        else 0
    )
    weekend_vs_weekday_var = (
        round(((weekday_avg - weekend_avg) / weekend_avg * 100), 1)
        if weekend_avg > 0
        else 0
    )

    # Comparaison période précédente (hors dimanche)
    prev_stats = prev_qs_no_sunday.aggregate(total=Sum("count"))
    prev_total = prev_stats["total"] or 0
    variation = round(
        ((open_total - prev_total) / prev_total * 100)
        if prev_total > 0
        else 100,
        1,
    )

    # Top 3 espaces (hors dimanche)
    top_locations = (
        filter_owned(
            VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date),
            request.user,
            field="location__user",
        )
        .exclude(date__week_day=1)
        .values("location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("-total")[:3]
    )

    # Données journalières (graphique principal)
    daily_data = qs.values("date").annotate(total=Sum("count")).order_by("date")

    # Données journalières période précédente (comparaison)
    prev_daily_data = (
        prev_qs.values("date").annotate(total=Sum("count")).order_by("date")
    )

    # Données par espace (hors dimanche)
    by_location = (
        filter_owned(
            VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date),
            request.user,
            field="location__user",
        )
        .exclude(date__week_day=1)
        .values("location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("-total")
    )

    # Données journalières par espace (barres empilées)
    daily_by_location = (
        filter_owned(
            VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date),
            request.user,
            field="location__user",
        )
        .values("date", "location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("date")
    )

    # Transformer en format stacked: { date: { loc_name: count } }
    stacked_raw = {}
    stacked_locations = []
    stacked_colors = []
    seen = set()
    for d in daily_by_location:
        date_key = d["date"].strftime("%d/%m")
        stacked_raw.setdefault(date_key, {})
        stacked_raw[date_key][d["location__name"]] = d["total"]
        if d["location__name"] not in seen:
            stacked_locations.append(d["location__name"])
            stacked_colors.append(d["location__color"])
            seen.add(d["location__name"])

    # Préparer les données Chart.js
    chart_labels = [d["date"].strftime("%d/%m") for d in daily_data]
    chart_values = [d["total"] for d in daily_data]
    day_names_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    chart_weekdays = [day_names_fr[d["date"].weekday()] for d in daily_data]

    # Construire les datasets pour les barres empilées
    stacked_datasets = []
    for loc_name, color in zip(stacked_locations, stacked_colors):
        data_row = []
        for label in chart_labels:
            data_row.append(stacked_raw.get(label, {}).get(loc_name, 0))
        if any(v > 0 for v in data_row):
            stacked_datasets.append(
                {"label": loc_name, "data": data_row, "backgroundColor": color}
            )

    # Supprimer la comparaison d'espaces (remplacée par le filtre personnalisé)
    # Courbe cumulée
    cumulative = []
    running = 0
    for v in chart_values:
        running += v
        cumulative.append(running)

    # Projection fin de mois (uniquement pour this_month)
    projection = None
    if period == "this_month":
        days_done = len(chart_values)
        month_days = (end_date - start_date).days + 1
        days_left = month_days - days_done
        daily_avg_proj = total_visitors / days_done if days_done > 0 else 0
        projection = (
            round(total_visitors + daily_avg_proj * days_left)
            if days_left > 0
            else total_visitors
        )

    chart_prev_values = None
    if prev_daily_data:
        chart_prev_values = []
        prev_map = {d["date"]: d["total"] for d in prev_daily_data}
        for d in daily_data:
            offset = d["date"] - timedelta(days=period_length)
            val = prev_map.get(offset)
            chart_prev_values.append(val if val is not None else 0)

    # Plus utilisé (remplacé par la période personnalisée)
    # pie_labels/pie_values/pie_colors supprimés (barres empilées à la place)

    # Tendances
    if len(chart_values) >= 2:
        first_half = chart_values[: len(chart_values) // 2]
        second_half = chart_values[len(chart_values) // 2 :]
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        trend = (
            "up"
            if avg_second > avg_first
            else ("down" if avg_second < avg_first else "stable")
        )
        trend_pct = (
            round(((avg_second - avg_first) / avg_first * 100), 1)
            if avg_first > 0
            else 0
        )
    else:
        trend = "stable"
        trend_pct = 0

    # Top 5 records
    top_days = daily_totals[:5]

    # ---- 1. Espaces pour le filtre dropdown ----
    locations = filter_location_owned(
        Location.objects.filter(is_active=True), request.user
    ).order_by("order", "name")

    # ---- 2. Comparaison N-1 (même période, année précédente) ----
    n1_start_date = start_date.replace(year=start_date.year - 1)
    n1_end_date = end_date.replace(year=end_date.year - 1)
    n1_qs = filter_owned(
        VisitorCount.objects.filter(
            date__gte=n1_start_date, date__lte=n1_end_date
        ).exclude(date__week_day=1),
        request.user, field="location__user",
    )
    if selected_location:
        n1_qs = n1_qs.filter(location=selected_location)
    n1_total = n1_qs.aggregate(total=Sum("count"))["total"] or 0
    n1_variation = round(
        ((total_visitors - n1_total) / n1_total * 100) if n1_total > 0 else 0, 1,
    )

    # ---- 3. Totaux par semaine ----
    from collections import defaultdict
    weekly_buckets = defaultdict(int)
    for d in daily_data:
        iso = d["date"].isocalendar()
        weekly_buckets[(iso[0], iso[1])] += d["total"]
    sorted_weeks = sorted(weekly_buckets)
    week_labels = [f"S{num}" for _, num in sorted_weeks]
    week_values = [weekly_buckets[k] for k in sorted_weeks]

    # ---- 5. Meilleure et pire semaine (7 jours consécutifs) ----
    best_week = None
    worst_week = None
    if chart_values:
        daily_map = {d["date"]: d["total"] for d in daily_data}
        full_values = []
        cur = start_date
        while cur <= end_date:
            full_values.append(daily_map.get(cur, 0))
            cur += timedelta(days=1)

        if len(full_values) >= 7:
            best_total = -1
            best_ix = 0
            worst_total = float("inf")
            worst_ix = 0
            for i in range(len(full_values) - 6):
                window = sum(full_values[i:i + 7])
                if window > best_total:
                    best_total = window
                    best_ix = i
                if window < worst_total:
                    worst_total = window
                    worst_ix = i

            best_week = {
                "start": start_date + timedelta(days=best_ix),
                "end": start_date + timedelta(days=best_ix + 6),
                "total": best_total,
            }
            worst_week = {
                "start": start_date + timedelta(days=worst_ix),
                "end": start_date + timedelta(days=worst_ix + 6),
                "total": worst_total,
            }

    # ---- 6. Flop 3 espaces (les moins fréquentés) ----
    bottom_locations = list(
        filter_owned(
            VisitorCount.objects.filter(
                date__gte=start_date, date__lte=end_date
            ),
            request.user,
            field="location__user",
        )
        .exclude(date__week_day=1)
        .values("location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("total")[:3]
    )

    # ---- Jours d'animation (espaces "Animation(s)", hors dimanche) ----
    # Convention : 1 jour avec pointages > 0 sur un espace Animation = 1 jour
    # d'animation (on ne peut pas distinguer plusieurs seances le meme jour).
    anim_rows = qs.exclude(date__week_day=1).filter(
        location__name__icontains="animation", count__gt=0
    )
    anim_agg = anim_rows.aggregate(
        total=Sum("count"), days=Count("date", distinct=True)
    )
    anim_total = anim_agg["total"] or 0
    anim_days = anim_agg["days"] or 0
    anim_avg = round(anim_total / anim_days, 1) if anim_days else 0
    has_animation_space = (
        filter_location_owned(
            Location.objects.filter(is_active=True), request.user
        )
        .filter(name__icontains="animation")
        .exists()
    )

    context = {
        "form": form,
        "start_date": start_date,
        "end_date": end_date,
        "period_length": period_length,
        "open_days": open_days,
        "closure_days": closure_days,
        "missing_days": missing_days,
        "completeness": completeness,
        "exceptional_total": exceptional_total,
        "opening_weekdays": opening_weekdays,
        "closure_aware": closure_aware,
        "period": period,
        "selected_location": selected_location,
        "total_visitors": total_visitors,
        "avg_per_day": avg_per_day,
        "days_with_data": days_with_data,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "chart_weekdays": chart_weekdays,
        "chart_prev_values": chart_prev_values,
        "stacked_datasets": stacked_datasets,
        "stacked_locations": stacked_locations,
        "by_location": by_location,
        "best_day": best_day,
        "worst_day": worst_day,
        "record_day": record_day,
        "weekday_avg_list": weekday_avg_list,
        "max_wavg": max_wavg,
        "best_weekday": best_weekday,
        "worst_weekday": worst_weekday,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "weekend_vs_weekday_var": weekend_vs_weekday_var,
        "cumulative": cumulative,
        "projection": projection,
        "prev_total": prev_total,
        "variation": variation,
        "top_locations": top_locations,
        "trend": trend,
        "trend_pct": trend_pct,
        "top_days": top_days,
        "locations": locations,
        "n1_total": n1_total,
        "n1_variation": n1_variation,
        "week_labels": week_labels,
        "week_values": week_values,
        "best_week": best_week,
        "worst_week": worst_week,
        "bottom_locations": bottom_locations,
        "anim_total": anim_total,
        "anim_days": anim_days,
        "anim_avg": anim_avg,
        "has_animation_space": has_animation_space,
        "current_year": timezone.now().year,
        "title": "Statistiques visiteurs",
    }

    return render(request, "visitor_tracking/statistics.html", context)


@mediatheque_member_required
def export_csv(request):
    """Exporter les données en CSV"""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    location_id = request.GET.get("location")

    today = timezone.now().date()

    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            start_date = today - timedelta(days=30)
    else:
        period = request.GET.get("period", "30_days")
        if period == "7_days":
            start_date = today - timedelta(days=7)
        elif period == "this_month":
            start_date = today.replace(day=1)
        elif period == "this_year":
            start_date = today.replace(month=1, day=1)
        else:
            start_date = today - timedelta(days=30)

    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            end_date = today
    else:
        end_date = today

    # Requête
    queryset = filter_owned(
        VisitorCount.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).select_related("location"),
        request.user,
        field="location__user",
    ).order_by("date", "location__order")

    if location_id:
        queryset = queryset.filter(location_id=location_id)

    # Créer la réponse CSV
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="visiteurs_{start_date}_{end_date}.csv"'
    )

    # BOM UTF-8 pour Excel
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Date", "Espace", "Nombre de visiteurs"])

    for entry in queryset:
        writer.writerow(
            [entry.date.strftime("%d/%m/%Y"), entry.location.name, entry.count]
        )

    return response


@mediatheque_member_required
def history(request):
    """Historique des pointages avec possibilité de modification"""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    location_filter = request.GET.get("location")

    sort = request.GET.get("sort", "date")
    order = request.GET.get("order", "desc")

    SORT_MAP = {
        "date": "date",
        "location": "location__name",
        "count": "count",
        "updated_at": "updated_at",
    }
    if sort not in SORT_MAP:
        sort = "date"

    order_field = SORT_MAP[sort]
    current_order = order
    if order == "desc":
        order_field = f"-{order_field}"

    queryset = filter_owned(
        VisitorCount.objects.select_related("location", "created_by", "updated_by"),
        request.user,
        field="location__user",
    )

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            queryset = queryset.filter(date__gte=date_from_obj)
        except ValueError:
            date_from = None

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            queryset = queryset.filter(date__lte=date_to_obj)
        except ValueError:
            date_to = None

    if location_filter:
        queryset = queryset.filter(location_id=location_filter)

    stats_agg = queryset.aggregate(
        total_visitors=Sum("count"),
        total_days=Count("date", distinct=True),
    )
    total_visitors = stats_agg["total_visitors"] or 0
    total_days = stats_agg["total_days"] or 0
    avg_per_day = round(total_visitors / total_days) if total_days > 0 else 0
    best_day = queryset.order_by("-count").first()

    # Listes pour les filtres (déclarées ici pour être utilisées par le graphique)
    locations = filter_location_owned(
        Location.objects.filter(is_active=True), request.user
    ).order_by("order", "name")

    # Données du graphique (uniquement si un lieu est sélectionné)
    selected_location_name = ""
    chart_labels = []
    chart_values = []
    chart_weekdays = []

    if location_filter:
        selected_location = locations.filter(id=location_filter).first()
        if selected_location:
            selected_location_name = selected_location.name

        today = timezone.now().date()

        try:
            chart_start = (
                datetime.strptime(date_from, "%Y-%m-%d").date()
                if date_from else today - timedelta(days=30)
            )
        except ValueError:
            chart_start = today - timedelta(days=30)

        try:
            chart_end = (
                datetime.strptime(date_to, "%Y-%m-%d").date()
                if date_to else today
            )
        except ValueError:
            chart_end = today

        chart_qs = filter_owned(
            VisitorCount.objects.filter(
                date__gte=chart_start,
                date__lte=chart_end,
                location_id=location_filter,
            ),
            request.user,
            field="location__user",
        ).values("date").annotate(total=Sum("count")).order_by("date")

        data_map = {d["date"]: d["total"] for d in chart_qs}
        if any(data_map.values()):
            day_names_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            d = chart_start
            while d <= chart_end:
                chart_labels.append(d.strftime("%d/%m"))
                chart_weekdays.append(day_names_fr[d.weekday()])
                chart_values.append(data_map.get(d, 0))
                d += timedelta(days=1)

    queryset = queryset.order_by(order_field, "location__order")

    paginator = Paginator(queryset, 50)
    page = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "page_obj": page_obj,
        "locations": locations,
        "date_from": date_from,
        "date_to": date_to,
        "location_filter": location_filter,
        "sort": sort,
        "order": current_order,
        "total_visitors": total_visitors,
        "total_days": total_days,
        "avg_per_day": avg_per_day,
        "best_day": best_day,
        "selected_location_name": selected_location_name,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "chart_weekdays": chart_weekdays,
        "title": "Historique des pointages",
    }

    return render(request, "visitor_tracking/history.html", context)


@mediatheque_member_required
def heatmap(request, year=None):
    """Calendrier heatmap annuel et qualification des jours sans pointage."""
    today = timezone.now().date()
    if not year:
        try:
            year = int(request.GET.get("year", today.year))
        except (ValueError, TypeError):
            year = today.year

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    location_filter = request.GET.get("location")

    available_communes = []
    if request.user.is_superuser:
        available_communes = SuperadminStatisticsService.get_available_communes()
    commune = (request.GET.get("commune") or "").strip()
    if commune not in {u.username for u in available_communes}:
        commune = ""

    # La validation se fait toujours pour une médiathèque précise.
    first_calendar_year = getattr(
        settings, "VISITOR_REPORT_V2_FROM_YEAR", 2026
    )
    scope_user = None
    can_validate = False
    if request.user.is_superuser:
        if commune:
            scope_user = next(
                (u for u in available_communes if u.username == commune),
                None,
            )
            can_validate = (
                scope_user is not None
                and year >= first_calendar_year
            )
    else:
        scope_user = request.user
        can_validate = year >= first_calendar_year

    opening_weekdays = (
        get_opening_weekdays(scope_user)
        if scope_user
        else list(DEFAULT_OPENING_WEEKDAYS)
    )
    if year < first_calendar_year:
        opening_weekdays = list(DEFAULT_OPENING_WEEKDAYS)
    closure_map = (
        build_closure_map(scope_user, start_date, end_date)
        if scope_user
        else {}
    )
    sunday_param = request.GET.get("dimanche")
    include_sunday = (
        6 in opening_weekdays
        if sunday_param is None
        else sunday_param == "1"
    )

    scope_qs = filter_owned(
        VisitorCount.objects.filter(
            date__gte=start_date, date__lte=end_date
        ),
        request.user,
        field="location__user",
    )
    if commune:
        scope_qs = scope_qs.filter(location__user__username=commune)
    pointed_dates = set(scope_qs.values_list("date", flat=True))

    qs = scope_qs
    if location_filter:
        qs = qs.filter(location_id=location_filter)

    daily_data = qs.values("date").annotate(total=Sum("count")).order_by("date")
    count_map = {d["date"]: d["total"] for d in daily_data}
    max_count = max(count_map.values()) if count_map else 0

    months = SuperadminStatisticsService.build_calendar_months(
        year,
        count_map,
        max_count,
        include_sunday=include_sunday,
        opening_weekdays=opening_weekdays,
        closure_map=closure_map,
        pointed_dates=pointed_dates,
        today=today,
    )

    breakdown_commune = commune or None
    if not request.user.is_superuser:
        breakdown_commune = request.user.username
    breakdown = SuperadminStatisticsService.get_breakdown_by_date(
        start_date,
        end_date,
        commune=breakdown_commune,
        location_filter=location_filter,
    )
    show_commune = request.user.is_superuser and not commune
    SuperadminStatisticsService.attach_tooltips(months, breakdown, show_commune)

    _days_fr = [
        "lundi", "mardi", "mercredi", "jeudi",
        "vendredi", "samedi", "dimanche",
    ]
    _months_fr = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    tooltip_map = {}
    missing_dates = []
    for _month in months:
        for _week in _month["weeks"]:
            for _cell in _week:
                if not _cell:
                    continue
                _d = _cell["date"]
                _label = (
                    f"{_days_fr[_d.weekday()]} {_d.day} "
                    f"{_months_fr[_d.month - 1]} {_d.year}"
                )
                _cell["label_fr"] = _label
                _entries = breakdown.get(_d, [])
                _lines = []
                for _e in _entries[:6]:
                    _where = (
                        f"{_e['commune'].capitalize()} — {_e['espace']}"
                        if show_commune
                        else _e["espace"]
                    )
                    _lines.append({"label": _where, "count": _e["count"] or 0})
                _extra = len(_entries) - len(_lines)
                closure = _cell.get("closure")
                closure_info = None
                if closure is not None:
                    closure_info = {
                        "id": closure.id,
                        "kind": closure.kind,
                        "label": closure.get_kind_display(),
                        "detail": closure.label,
                        "start": closure.start_date.isoformat(),
                        "end": closure.end_date.isoformat(),
                    }
                if _cell["is_missing"]:
                    missing_dates.append(_d)
                tooltip_map[_d.isoformat()] = {
                    "label": _label,
                    "total": _cell["count"] or 0,
                    "lines": _lines,
                    "extra": _extra if _extra > 0 else 0,
                    "state": _cell["state"],
                    "state_label": _cell["state_label"],
                    "has_pointage": _cell["has_pointage"],
                    "closure": closure_info,
                }

    missing_dates.sort()
    missing_by_month = {}
    for day in missing_dates:
        missing_by_month.setdefault(day.strftime("%Y-%m"), []).append(day)
    missing_groups = [
        {
            "label": (
                f"{_months_fr[days[0].month - 1].capitalize()} "
                f"{days[0].year}"
            ),
            "dates": days,
        }
        for _, days in sorted(missing_by_month.items())
    ]

    query_params = []
    if commune:
        query_params.append(f"commune={commune}")
    if location_filter:
        query_params.append(f"location={location_filter}")
    query_params.append(
        f"dimanche={'1' if include_sunday else '0'}"
    )
    query_suffix = "?" + "&".join(query_params) if query_params else ""

    locations = filter_location_owned(
        Location.objects.filter(is_active=True), request.user
    ).select_related("user")
    if commune:
        locations = locations.filter(user__username=commune)
    locations = locations.order_by("order", "name")

    closures = (
        list(get_closures(scope_user, start_date, end_date))
        if scope_user
        else []
    )

    context = {
        "year": year,
        "prev_year": year - 1,
        "next_year": year + 1,
        "months": months,
        "max_count": max_count,
        "locations": locations,
        "location_filter": location_filter,
        "commune": commune,
        "available_communes": available_communes,
        "show_commune_prefix": request.user.is_superuser and not commune,
        "today": today,
        "title": f"Calendrier {year}",
        "heatmap_tooltips": tooltip_map,
        "opening_weekdays": opening_weekdays,
        "opening_weekday_labels": WEEKDAY_LABELS,
        "include_sunday": include_sunday,
        "can_validate": can_validate,
        "scope_username": scope_user.username if scope_user else "",
        "closure_map": closure_map,
        "closures": closures,
        "missing_dates": missing_dates,
        "missing_by_month": missing_by_month,
        "missing_groups": missing_groups,
        "missing_count": len(missing_dates),
        "closure_kinds": Closure.KIND_CHOICES,
        "query_suffix": query_suffix,
        "calendar_first_year": first_calendar_year,
    }

    return render(request, "visitor_tracking/heatmap.html", context)


def _heatmap_scope(request, year):
    """Médiathèque ciblée par une action de qualification."""
    first_year = getattr(settings, "VISITOR_REPORT_V2_FROM_YEAR", 2026)
    if year < first_year:
        return (
            None,
            "La qualification des jours est disponible à partir de "
            f"{first_year}.",
        )
    if request.user.is_superuser:
        commune = (
            request.POST.get("commune")
            or request.GET.get("commune")
            or ""
        ).strip()
        if not commune:
            return None, "Sélectionnez une médiathèque."
        user = (
            User.objects.filter(
                username=commune, locations__isnull=False
            )
            .distinct()
            .first()
        )
        if user is None:
            return None, "Médiathèque inconnue."
        return user, ""
    return request.user, ""


@mediatheque_member_required
@require_POST
def heatmap_create_closures(request, year):
    """Crée une ou plusieurs fermetures à partir des jours sélectionnés."""
    scope_user, error = _heatmap_scope(request, year)
    if scope_user is None:
        return JsonResponse({"error": error}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Données invalides."}, status=400)

    raw_dates = payload.get("dates") or []
    kind = payload.get("kind") or "exceptional"
    label = (payload.get("label") or "").strip()[:200]
    valid_kinds = {choice[0] for choice in Closure.KIND_CHOICES}
    if kind not in valid_kinds:
        return JsonResponse({"error": "Motif inconnu."}, status=400)
    if not isinstance(raw_dates, list) or not raw_dates:
        return JsonResponse(
            {"error": "Aucun jour sélectionné."}, status=400
        )

    dates = []
    for raw_date in raw_dates:
        try:
            day = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        if day.year == year:
            dates.append(day)
    dates = sorted(set(dates))
    if not dates:
        return JsonResponse({"error": "Aucune date valide."}, status=400)

    opening_weekdays = get_opening_weekdays(scope_user)
    closure_map = build_closure_map(
        scope_user, date(year, 1, 1), date(year, 12, 31)
    )
    pointed = set(
        VisitorCount.objects.filter(
            location__user=scope_user,
            date__in=dates,
        ).values_list("date", flat=True)
    )

    valid = []
    skipped = []
    for day in dates:
        if (
            day.weekday() not in opening_weekdays
            or day in closure_map
            or day in pointed
        ):
            skipped.append(day.isoformat())
        else:
            valid.append(day)

    if not valid:
        return JsonResponse(
            {
                "created": 0,
                "skipped": skipped,
                "error": "Aucun jour éligible.",
            },
            status=400,
        )

    ranges = []
    with transaction.atomic():
        for start_date, end_date in group_dates_into_ranges(valid):
            Closure.objects.create(
                user=scope_user,
                start_date=start_date,
                end_date=end_date,
                kind=kind,
                label=label,
                created_by=request.user,
            )
            ranges.append(
                {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                }
            )

    return JsonResponse(
        {"created": len(ranges), "ranges": ranges, "skipped": skipped}
    )


@mediatheque_member_required
@require_POST
def heatmap_delete_closure(request, year, closure_id):
    """Rouvre un jour, ou supprime toute une fermeture."""
    scope_user, error = _heatmap_scope(request, year)
    if scope_user is None:
        return JsonResponse({"error": error}, status=400)

    closure = get_object_or_404(
        Closure, id=closure_id, user=scope_user
    )
    if not (
        closure.start_date.year == year
        or closure.end_date.year == year
    ):
        return JsonResponse(
            {"error": "Fermeture hors de l'année affichée."}, status=400
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        payload = {}

    raw_date = payload.get("date")
    if raw_date:
        try:
            day = date.fromisoformat(str(raw_date))
        except ValueError:
            return JsonResponse({"error": "Date invalide."}, status=400)
        if not (closure.start_date <= day <= closure.end_date):
            return JsonResponse(
                {"error": "Date hors de la fermeture."}, status=400
            )
        if closure.start_date == closure.end_date:
            closure.delete()
        elif day == closure.start_date:
            closure.start_date = day + timedelta(days=1)
            closure.save()
        elif day == closure.end_date:
            closure.end_date = day - timedelta(days=1)
            closure.save()
        else:
            with transaction.atomic():
                before = Closure.objects.create(
                    user=scope_user,
                    start_date=closure.start_date,
                    end_date=day - timedelta(days=1),
                    kind=closure.kind,
                    label=closure.label,
                    created_by=request.user,
                )
                after = Closure.objects.create(
                    user=scope_user,
                    start_date=day + timedelta(days=1),
                    end_date=closure.end_date,
                    kind=closure.kind,
                    label=closure.label,
                    created_by=request.user,
                )
                closure.delete()
            return JsonResponse(
                {
                    "reopened": day.isoformat(),
                    "split": [before.id, after.id],
                }
            )
        return JsonResponse({"reopened": day.isoformat()})

    closure.delete()
    return JsonResponse({"deleted": closure_id})


@mediatheque_member_required
@require_POST
def heatmap_opening_days(request, year):
    """Met à jour les jours d'ouverture habituels de la médiathèque."""
    scope_user, error = _heatmap_scope(request, year)
    if scope_user is None:
        messages.error(request, error)
        return redirect("visitor_tracking:heatmap_year", year=year)

    days = set()
    for raw_day in request.POST.getlist("weekdays"):
        try:
            day = int(raw_day)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6:
            days.add(day)
    if not days:
        messages.error(
            request, "Sélectionnez au moins un jour d'ouverture."
        )
        return redirect("visitor_tracking:heatmap_year", year=year)

    profile, _ = LibraryProfile.objects.get_or_create(
        user=scope_user,
        defaults={"name": scope_user.username.capitalize()},
    )
    profile.opening_weekdays = sorted(days)
    profile.save()

    messages.success(request, "Jours d'ouverture mis à jour.")
    url = reverse("visitor_tracking:heatmap_year", args=[year])
    params = []
    if request.user.is_superuser:
        params.append(f"commune={scope_user.username}")
    location_filter = request.POST.get("location")
    if location_filter:
        params.append(f"location={location_filter}")
    params.append(f"dimanche={'1' if 6 in days else '0'}")
    return redirect(f"{url}?{'&'.join(params)}")


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_heatmap(request, year=None):
    """Calendrier de fréquentation annuel — réservé aux superadmins."""
    if not year:
        try:
            year = int(request.GET.get("year", timezone.now().year))
        except (ValueError, TypeError):
            year = timezone.now().year

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    available_communes = SuperadminStatisticsService.get_available_communes()
    commune = (request.GET.get("commune") or "").strip()
    if commune not in {u.username for u in available_communes}:
        commune = ""

    location_filter = request.GET.get("location")

    qs = VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date)
    if commune:
        qs = qs.filter(location__user__username=commune)
    if location_filter:
        qs = qs.filter(location_id=location_filter)

    daily_data = qs.values("date").annotate(total=Sum("count")).order_by("date")
    count_map = {d["date"]: d["total"] for d in daily_data}
    max_count = max(count_map.values()) if count_map else 0

    months = SuperadminStatisticsService.build_calendar_months(
        year, count_map, max_count
    )
    breakdown = SuperadminStatisticsService.get_breakdown_by_date(
        start_date,
        end_date,
        commune=commune or None,
        location_filter=location_filter,
    )
    SuperadminStatisticsService.attach_tooltips(months, breakdown, not commune)

    # Carte des infobulles riches : {date_iso: {label, total, lines[]}}.
    _days_fr = [
        "lundi", "mardi", "mercredi", "jeudi",
        "vendredi", "samedi", "dimanche",
    ]
    _months_fr = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    tooltip_map = {}
    for _month in months:
        for _week in _month["weeks"]:
            for _cell in _week:
                if not _cell:
                    continue
                _d = _cell["date"]
                _label = (
                    f"{_days_fr[_d.weekday()]} {_d.day} "
                    f"{_months_fr[_d.month - 1]} {_d.year}"
                )
                _cell["label_fr"] = _label
                _entries = breakdown.get(_d, [])
                _lines = []
                for _e in _entries[:6]:
                    _where = (
                        f"{_e['commune'].capitalize()} — {_e['espace']}"
                        if not commune
                        else _e["espace"]
                    )
                    _lines.append({"label": _where, "count": _e["count"] or 0})
                _extra = len(_entries) - len(_lines)
                tooltip_map[_d.isoformat()] = {
                    "label": _label,
                    "total": _cell["count"] or 0,
                    "lines": _lines,
                    "extra": _extra if _extra > 0 else 0,
                }

    locations = Location.objects.filter(is_active=True).select_related("user")
    if commune:
        locations = locations.filter(user__username=commune)
    locations = locations.order_by("order", "name")

    data_years = [d.year for d in VisitorCount.objects.dates("date", "year")]
    years = sorted(set(data_years) | {timezone.now().year})

    context = {
        "year": year,
        "years": years,
        "prev_year": year - 1,
        "next_year": year + 1,
        "months": months,
        "max_count": max_count,
        "locations": locations,
        "location_filter": location_filter,
        "commune": commune,
        "available_communes": available_communes,
        "show_commune_prefix": not commune,
        "today": timezone.now().date(),
        "title": f"Calendrier {year}",
        "heatmap_tooltips": tooltip_map,
    }

    return render(request, "visitor_tracking/superadmin_heatmap.html", context)


def _report_year(request, year):
    """Année du rapport, avec repli sur l'année en cours."""
    if year is None:
        year = request.GET.get("year")
    try:
        value = int(year)
    except (TypeError, ValueError):
        value = timezone.now().year
    if value < 1900 or value > 2100:
        value = timezone.now().year
    return value


def _report_context(request, year=None):
    """Contexte commun à l'écran, à l'impression et aux exports."""
    today = timezone.now().date()
    year = _report_year(request, year)

    vue = request.GET.get("vue", "synthese")
    if vue not in ("synthese", "detail"):
        vue = "synthese"

    commune = (request.GET.get("commune") or "").strip()
    available_communes = []
    scope_user = request.user

    if request.user.is_superuser:
        available_communes = AnnualReportService.get_available_communes()
        scope_user = next(
            (user for user in available_communes if user.username == commune),
            None,
        )
        if scope_user is None:
            return None, {
                "year": year,
                "vue": vue,
                "commune": "",
                "available_communes": available_communes,
                "needs_commune": True,
                "today": today,
                "title": f"Rapport annuel {year}",
            }
    else:
        commune = ""

    report = AnnualReportService(
        year,
        scope_user,
        is_superuser=request.user.is_superuser,
        today=today,
    ).build()

    data_years = VisitorCount.objects.filter(
        location__user=scope_user
    ).dates("date", "year")
    years = sorted(
        {item.year for item in data_years} | {today.year, year}
    )

    context = {
        "report": report,
        "year": year,
        "vue": vue,
        "commune": commune if request.user.is_superuser else "",
        "available_communes": available_communes,
        "years": years,
        "prev_year": year - 1 if year > 1900 else None,
        "next_year": year + 1 if year < today.year else None,
        "current_year": today.year,
        "today": today,
        "title": (
            f"{'Bilan' if vue == 'synthese' else 'Rapport'} "
            f"d'activité {year}"
        ),
        # Alias de compatibilité avec les tests et anciens liens.
        "monthly": report["monthly"],
        "yearly_top": report["spaces"][:5],
        "synthese": report["synthese"],
        "total_year": report["totals"]["total"],
        "n1_total": report["totals"]["n1_total"],
        "variation": report["totals"]["variation"],
        "avg_per_day": report["totals"]["avg_per_pointed_day"],
        "days_count": report["totals"]["pointed_days"],
        "weekday_avg": report["weekday"],
        "quarterly": {
            item["name"]: item["total"] for item in report["quarterly"]
        },
        "best_days": report["top_days"],
    }
    return context, None


@mediatheque_member_required
def annual_report(request, year=None):
    """Rapport annuel de fréquentation, par médiathèque."""
    context, chooser = _report_context(request, year)
    if chooser:
        return render(
            request,
            "visitor_tracking/annual_report_chooser.html",
            chooser,
        )
    return render(
        request,
        "visitor_tracking/annual_report.html",
        context,
    )


@mediatheque_member_required
def annual_report_print(request, year=None):
    """Version imprimable (PDF via la boîte d'impression du navigateur)."""
    context, chooser = _report_context(request, year)
    if chooser:
        return render(
            request,
            "visitor_tracking/annual_report_chooser.html",
            chooser,
        )
    context["print_mode"] = True
    return render(
        request,
        "visitor_tracking/annual_report_print.html",
        context,
    )


def _csv_num(value):
    """Nombre au format français pour les CSV ouverts dans Excel."""
    if value is None or value == "":
        return ""
    return str(value).replace(".", ",")


def _csv_report_response(report, year, kind):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    label = slugify(report["scope"]["label"]) or "mediatheque"
    filename = (
        f"donnees_{label}_{year}.csv"
        if kind == "csv-donnees"
        else f"synthese_{label}_{year}.csv"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")

    if kind == "csv-donnees":
        writer.writerow(["Date", "Espace", "Nombre de visiteurs"])
        rows = (
            VisitorCount.objects.filter(
                location__user__username=report["scope"]["username"],
                date__gte=report["period"]["start"],
                date__lte=report["period"]["end"],
            )
            .select_related("location")
            .order_by("date", "location__order", "location__name")
        )
        for entry in rows:
            writer.writerow(
                [
                    entry.date.strftime("%d/%m/%Y"),
                    entry.location.name,
                    entry.count,
                ]
            )
        return response

    writer.writerow(
        [
            "Type",
            "Libellé",
            "Total",
            "N-1",
            "Variation (%)",
            "Part (%)",
        ]
    )
    totals = report["totals"]
    writer.writerow(
        [
            "Synthèse",
            "Total visiteurs",
            totals["total"],
            totals["n1_total"],
            _csv_num(totals["variation"]),
            "",
        ]
    )
    writer.writerow(
        [
            "Synthèse",
            "Jours pointés",
            totals["pointed_days"],
            "",
            "",
            "",
        ]
    )
    for month in report["monthly"]:
        writer.writerow(
            [
                "Mois",
                month["month"],
                month["total"],
                month["n1"],
                _csv_num(month["variation"]),
                _csv_num(month["share"]),
            ]
        )
    for space in report["spaces"]:
        writer.writerow(
            [
                "Espace",
                space["name"],
                space["total"],
                space["n1"],
                _csv_num(space["variation"]),
                _csv_num(space["share"]),
            ]
        )
    for closure in report.get("closure_rows", []):
        label = closure["kind_label"]
        if closure["label"]:
            label = f"{label} — {closure['label']}"
        writer.writerow(
            [
                "Fermeture",
                label,
                closure["days"],
                "",
                "",
                "",
            ]
        )
    return response


@mediatheque_member_required
def annual_report_export(request, year, kind):
    """Export DOCX ou CSV du rapport annuel."""
    if kind not in (
        "docx-synthese",
        "docx-detail",
        "csv-synthese",
        "csv-donnees",
    ):
        return HttpResponseBadRequest("Format d'export inconnu.")

    context, chooser = _report_context(request, year)
    if chooser:
        return HttpResponseBadRequest(
            "Sélectionnez une médiathèque avant de télécharger le rapport."
        )

    report = context["report"]
    if kind in ("csv-synthese", "csv-donnees"):
        return _csv_report_response(report, year, kind)

    doc = build_annual_report_docx(
        report,
        detailed=kind == "docx-detail",
    )
    label = slugify(report["scope"]["label"]) or "mediatheque"
    prefix = "bilan" if kind == "docx-synthese" else "rapport"
    filename = f"{prefix}_{label}_{year}.docx"
    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    doc.save(response)
    return response


@mediatheque_member_required
def edit_entry(request, entry_id):
    """Modifier un pointage existant"""
    entry = get_object_or_404(
        filter_owned(VisitorCount.objects.all(), request.user, field="location__user"),
        id=entry_id,
    )

    if request.method == "POST":
        new_count = request.POST.get("count")
        try:
            new_count = int(new_count)
            if new_count >= 0:
                entry.count = new_count
                entry.updated_by = request.user
                entry.save()
                messages.success(
                    request,
                    f"Comptage modifié : {entry.location.name} - "
                    f"{entry.date.strftime('%d/%m/%Y')} = {new_count}",
                )
            else:
                messages.error(request, "Le nombre doit être positif.")
        except (ValueError, TypeError):
            messages.error(request, "Valeur invalide.")

        return redirect("visitor_tracking:history")

    context = {"entry": entry, "title": f"Modifier - {entry.location.name}"}

    return render(request, "visitor_tracking/edit_entry.html", context)


@mediatheque_member_required_json
@require_POST
def delete_entry(request, entry_id):
    """Supprimer un pointage"""
    entry = get_object_or_404(
        filter_owned(VisitorCount.objects.all(), request.user, field="location__user"),
        id=entry_id,
    )
    entry.delete()

    return JsonResponse({"success": True})


@mediatheque_member_required
def add_space(request):
    """Ajouter un nouvel espace"""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        icon = request.POST.get("icon", "bx-building")
        color = request.POST.get("color", "#4F46E5")

        if name:
            if (
                filter_location_owned(Location.objects.all(), request.user)
                .filter(name__iexact=name)
                .exists()
            ):
                messages.error(request, f"L'espace '{name}' existe déjà.")
            else:
                max_order = (
                    filter_location_owned(
                        Location.objects.all(), request.user
                    ).aggregate(max_order=Max("order"))["max_order"]
                    or 0
                )

                Location.objects.create(
                    name=name,
                    description=description,
                    icon=icon,
                    color=color,
                    user=request.user,
                    order=max_order + 1,
                )
                messages.success(request, f"Espace '{name}' créé avec succès.")
                return redirect("visitor_tracking:index")
        else:
            messages.error(request, "Le nom de l'espace est obligatoire.")

    context = {
        "icons": SPACE_ICONS,
        "colors": SPACE_COLORS,
        "title": "Ajouter un espace",
    }
    return render(request, "visitor_tracking/add_space.html", context)


@mediatheque_member_required
def edit_space(request, location_id):
    """Modifier un espace existant"""
    location = get_object_or_404(
        filter_location_owned(Location.objects.all(), request.user), id=location_id
    )
    commune = ""
    if (
        request.user.is_superuser
        and location.user is not None
        and location.user != request.user
    ):
        commune = location.user.username

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        icon = request.POST.get("icon", "bx-building")
        color = request.POST.get("color", "#4F46E5")

        if name:
            duplicate = (
                filter_location_owned(Location.objects.all(), request.user)
                .filter(name__iexact=name)
                .exclude(id=location.id)
                .exists()
            )
            if duplicate:
                messages.error(request, f"L'espace '{name}' existe déjà.")
            else:
                location.name = name
                location.description = description
                location.icon = icon
                location.color = color
                location.save(update_fields=["name", "description", "icon", "color"])
                messages.success(request, f"Espace '{name}' modifié avec succès.")
                target = reverse("visitor_tracking:index")
                if commune:
                    target = f"{target}?commune={commune}"
                return redirect(target)
        else:
            messages.error(request, "Le nom de l'espace est obligatoire.")

    context = {
        "icons": SPACE_ICONS,
        "colors": SPACE_COLORS,
        "location": location,
        "commune": commune,
        "title": f"Modifier {location.name}",
    }
    return render(request, "visitor_tracking/add_space.html", context)


@mediatheque_member_required_json
@require_POST
def delete_space(request, location_id):
    """Supprimer un espace"""
    location = get_object_or_404(
        filter_location_owned(Location.objects.all(), request.user), id=location_id
    )
    name = location.name
    location.delete()

    return JsonResponse({"success": True, "message": f"Espace '{name}' supprimé."})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_statistics(request):
    """Page superadmin : stats globales + comparaison par médiathèque"""
    period = request.GET.get("period", "30_days")

    def parse_get_date(key):
        raw = request.GET.get(key)
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    start_date, end_date = SuperadminStatisticsService.compute_period(
        period,
        custom_start=parse_get_date("start_date"),
        custom_end=parse_get_date("end_date"),
    )

    available_communes = SuperadminStatisticsService.get_available_communes()

    # Filtre par commune (username = nom de la commune)
    commune = (request.GET.get("commune") or "").strip()
    if commune not in {u.username for u in available_communes}:
        commune = ""

    global_stats = SuperadminStatisticsService.get_global_stats(
        start_date, end_date, commune=commune or None
    )
    locations, grand_total = SuperadminStatisticsService.get_locations_comparison(
        start_date, end_date, commune=commune or None
    )
    stacked_data = SuperadminStatisticsService.get_stacked_chart_data(
        start_date, end_date, commune=commune or None
    )

    # Sections de comparaison entre médiathèques : uniquement en vue globale
    available_users = []
    selected_usernames = None
    users_comparison = []
    if not commune:
        # Utilisateurs disponibles pour le filtre
        available_users = SuperadminStatisticsService.get_available_users(
            start_date, end_date
        )

        # Comparaison par utilisateur (N médiathèques, sans mode duel)
        selected_usernames = request.GET.getlist("users") or None
        users_comparison = SuperadminStatisticsService.get_users_comparison(
            start_date, end_date, selected_usernames
        )

    # Données journalières par utilisateur (graphique multi-lignes)
    daily_by_user_qs = VisitorCount.objects.filter(
        date__gte=start_date, date__lte=end_date
    )
    if commune:
        daily_by_user_qs = daily_by_user_qs.filter(location__user__username=commune)
    daily_by_user = list(
        daily_by_user_qs.values("date", "location__user__username")
        .annotate(total=Sum("count"))
        .order_by("date")
    )

    all_dates_set = set()
    user_date_totals = {}
    palette = [
        "#4F46E5",
        "#7C3AED",
        "#EC4899",
        "#EF4444",
        "#F97316",
        "#22C55E",
        "#14B8A6",
        "#06B6D4",
        "#8B5CF6",
        "#3B82F6",
    ]

    def _user_color(username):
        """Couleur stable par utilisateur (déterministe, sans mapping en dur)."""
        h = int(hashlib.md5(username.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
        return palette[h % len(palette)]

    for row in daily_by_user:
        ds = row["date"].isoformat()
        uname = row["location__user__username"]
        all_dates_set.add(ds)
        if uname not in user_date_totals:
            user_date_totals[uname] = {}
        user_date_totals[uname][ds] = user_date_totals[uname].get(ds, 0) + (
            row["total"] or 0
        )

    all_dates = sorted(all_dates_set)
    chart_labels = all_dates
    chart_datasets = []
    for uname in sorted(user_date_totals.keys()):
        data_vals = [user_date_totals[uname].get(d, 0) for d in all_dates]
        chart_datasets.append(
            {
                "label": uname,
                "color": _user_color(uname),
                "data": data_vals,
            }
        )

    # Cumulé (global)
    daily_global = {
        ds: sum(ds_data.get(ds, 0) for ds_data in user_date_totals.values())
        for ds in all_dates
    }
    cumulative = []
    running = 0
    for d in all_dates:
        running += daily_global.get(d, 0)
        cumulative.append(running)

    period_length = (end_date - start_date).days or 1
    all_dates_objs = [date.fromisoformat(d) for d in all_dates]
    daily_totals = [daily_global.get(d, 0) for d in all_dates]

    # Comparaison période précédente (alignée jour par jour, ligne globale)
    prev_daily_map = SuperadminStatisticsService.get_prev_period_daily(
        start_date, end_date, commune=commune or None
    )
    chart_prev_values = [
        prev_daily_map.get(d - timedelta(days=period_length), 0) for d in all_dates_objs
    ]

    # Noms des jours (tooltips du graphique journalier)
    day_names_fr = [
        "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
    ]
    chart_weekdays = [day_names_fr[d.weekday()] for d in all_dates_objs]

    # Totaux par semaine (buckets ISO)
    weekly_buckets = defaultdict(int)
    for d_obj in all_dates_objs:
        iso = d_obj.isocalendar()
        weekly_buckets[(iso[0], iso[1])] += daily_global.get(d_obj.isoformat(), 0)
    sorted_weeks = sorted(weekly_buckets)
    week_labels = [f"S{num}" for _, num in sorted_weeks]
    week_values = [weekly_buckets[k] for k in sorted_weeks]

    # Meilleure et pire semaine (7 jours consécutifs, série zéro-fillée)
    best_week = None
    worst_week = None
    if all_dates_objs:
        data_map = {d: daily_global.get(d.isoformat(), 0) for d in all_dates_objs}
        full_values = []
        cur = start_date
        while cur <= end_date:
            full_values.append(data_map.get(cur, 0))
            cur += timedelta(days=1)

        if len(full_values) >= 7:
            best_total = -1
            best_ix = 0
            worst_total = float("inf")
            worst_ix = 0
            for i in range(len(full_values) - 6):
                window = sum(full_values[i : i + 7])
                if window > best_total:
                    best_total = window
                    best_ix = i
                if window < worst_total:
                    worst_total = window
                    worst_ix = i

            best_week = {
                "start": start_date + timedelta(days=best_ix),
                "end": start_date + timedelta(days=best_ix + 6),
                "total": best_total,
            }
            worst_week = {
                "start": start_date + timedelta(days=worst_ix),
                "end": start_date + timedelta(days=worst_ix + 6),
                "total": worst_total,
            }

    # vs Année N-1
    n1_stats = SuperadminStatisticsService.get_n1_stats(
        start_date, end_date, commune=commune or None
    )
    n1_total = n1_stats["total"]
    n1_variation = (
        round(((global_stats["total"] - n1_total) / n1_total * 100), 1)
        if n1_total > 0
        else 0
    )

    # Projection fin de mois (uniquement pour this_month)
    projection = None
    if period == "this_month" and daily_totals:
        days_done = len(daily_totals)
        month_days = (end_date - start_date).days + 1
        days_left = month_days - days_done
        total_so_far = sum(daily_totals)
        daily_avg_proj = total_so_far / days_done if days_done > 0 else 0
        projection = (
            round(total_so_far + daily_avg_proj * days_left)
            if days_left > 0
            else round(total_so_far)
        )

    # Libellés courts FR sur longues périodes (même longueur, alignement intact).
    if len(all_dates) > 60:
        chart_labels = [f"{d[8:10]}/{d[5:7]}" for d in all_dates]

    # Croisements mis en cache (contexte conservé quand un filtre est actif).
    cache_key = (
        f"superadmin_stats:{period}:{start_date.isoformat()}:"
        f"{end_date.isoformat()}:{commune or '-'}:v1"
    )
    cached_extra = cache.get(cache_key)
    if cached_extra is None:
        cached_extra = {
            "weekday_overview": SuperadminStatisticsService.get_weekday_overview(
                start_date, end_date, commune=commune or None
            ),
            "commune_month_matrix": SuperadminStatisticsService.get_commune_month_matrix(
                start_date, end_date, commune=commune or None
            ),
        }
        cache.set(cache_key, cached_extra, 300)

    # Synthèse narrative (données live, jamais cachée).
    _months_fr = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    _days_fr = [
        "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    ]

    def _date_fr(d):
        return f"{_days_fr[d.weekday()]} {d.day} {_months_fr[d.month - 1]}" if d else None

    _perimetre_parts = []
    if commune:
        _perimetre_parts.append(f"commune {commune.capitalize()}")
    if selected_usernames:
        _perimetre_parts.append(
            f"médiathèques : {', '.join(selected_usernames)}"
        )
    _best = global_stats.get("best_day") or {}
    _best_week = best_week or {}
    _top_loc = next((loc for loc in locations if loc["total"]), None)
    _mm = cached_extra.get("commune_month_matrix", {})
    _col_totals = [
        sum(row["months"][i] for row in _mm.get("matrix", []))
        for i in range(len(_mm.get("months", [])))
    ]
    _peak_month = None
    if _col_totals and any(_col_totals):
        _bi = _col_totals.index(max(_col_totals))
        _peak_month = (_mm["months"][_bi]["label"], _col_totals[_bi])
    synthese = SuperadminStatisticsService.build_synthese(
        {
            "start_label": start_date.strftime("%d/%m/%Y"),
            "end_label": end_date.strftime("%d/%m/%Y"),
            "total": global_stats["total"],
            "avg_per_day": global_stats["avg_per_day"],
            "days_with_data": global_stats["days_with_data"],
            "period_length": global_stats["period_length"],
            "variation": global_stats.get("variation"),
            "n1_total": n1_total,
            "n1_variation": n1_variation,
            "top_commune": (
                (
                    _top_loc["user"].capitalize(),
                    _top_loc["total"],
                    _top_loc["pct"],
                )
                if _top_loc
                else None
            ),
            "best_day": (
                (_date_fr(_best.get("date")), _best.get("total"))
                if _best.get("date")
                else None
            ),
            "best_weekday": (
                (global_stats.get("best_weekday") or {}).get("name")
            ),
            "best_week": (
                (
                    f"du {_best_week['start'].strftime('%d/%m')} "
                    f"au {_best_week['end'].strftime('%d/%m')}",
                    _best_week["total"],
                )
                if _best_week.get("start")
                else None
            ),
            "peak_month": _peak_month,
            "projection": projection,
            "perimetre": ", ".join(_perimetre_parts) or None,
        }
    )

    context = {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "period_length": period_length,
        "commune": commune,
        "available_communes": available_communes,
        "global_stats": global_stats,
        "locations": locations,
        "stacked_datasets": stacked_data["datasets"],
        "chart_labels": chart_labels,
        "chart_datasets": chart_datasets,
        "chart_prev_values": chart_prev_values,
        "chart_weekdays": chart_weekdays,
        "daily_totals": daily_totals,
        "cumulative": cumulative,
        "week_labels": week_labels,
        "week_values": week_values,
        "best_week": best_week,
        "worst_week": worst_week,
        "n1_total": n1_total,
        "n1_variation": n1_variation,
        "projection": projection,
        "weekday_overview": cached_extra["weekday_overview"],
        "commune_month_matrix": cached_extra["commune_month_matrix"],
        "synthese": synthese,
        "available_users": available_users,
        "selected_usernames": selected_usernames or [],
        "users_comparison": users_comparison,
        "has_active_filters": bool(commune or selected_usernames),
        "current_year": timezone.now().year,
    }
    return render(request, "visitor_tracking/superadmin_statistics.html", context)
