"""Calendrier d'ouverture : jours habituels et fermetures.

Ce module est la source unique pour savoir si une date est ouverte. Il est
utilisé par la heatmap, les statistiques, le rapport annuel et le pointage.
"""

from datetime import timedelta

from accounts.models import LibraryProfile
from .models import Closure

DEFAULT_OPENING_WEEKDAYS = [0, 1, 2, 3, 4, 5]

WEEKDAY_LABELS = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]

CLOSURE_KIND_PRIORITY = {
    "public_holiday": 0,
    "annual": 1,
    "works": 2,
    "exceptional": 3,
    "other": 4,
}


def get_opening_weekdays(user):
    """Jours d'ouverture habituels d'une médiathèque.

    Retourne une liste d'entiers 0=lundi ... 6=dimanche. Si le profil
    n'existe pas ou si la valeur est vide/invalide, on retombe sur
    lundi-samedi.
    """
    if user is None:
        return list(DEFAULT_OPENING_WEEKDAYS)
    try:
        profile = user.library_profile
    except LibraryProfile.DoesNotExist:
        return list(DEFAULT_OPENING_WEEKDAYS)

    raw_days = profile.opening_weekdays
    if not isinstance(raw_days, list):
        return list(DEFAULT_OPENING_WEEKDAYS)

    days = set()
    for value in raw_days:
        try:
            day = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6:
            days.add(day)
    return sorted(days) or list(DEFAULT_OPENING_WEEKDAYS)


def get_closures(user, start_date, end_date):
    """Fermetures qui chevauchent la période."""
    if user is None:
        return Closure.objects.none()
    return Closure.objects.filter(
        user=user,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).order_by("start_date", "end_date")


def _date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def build_closure_map(user, start_date, end_date):
    """Dict {date: Closure} pour toutes les dates fermées de la période.

    En cas de chevauchement, la fermeture la plus « prioritaire » est
    conservée (jour férié, puis fermeture annuelle, travaux, etc.).
    """
    result = {}
    for closure in get_closures(user, start_date, end_date):
        first = max(closure.start_date, start_date)
        last = min(closure.end_date, end_date)
        if first > last:
            continue
        for day in _date_range(first, last):
            existing = result.get(day)
            if existing is None or (
                CLOSURE_KIND_PRIORITY.get(closure.kind, 99)
                < CLOSURE_KIND_PRIORITY.get(existing.kind, 99)
            ):
                result[day] = closure
    return result


def get_open_dates(start_date, end_date, opening_weekdays, closure_map):
    """Dates réellement ouvertes : bon jour de semaine et non fermées."""
    open_dates = set()
    for day in _date_range(start_date, end_date):
        if day.weekday() in opening_weekdays and day not in closure_map:
            open_dates.add(day)
    return open_dates


def is_open_date(day, opening_weekdays, closure_map):
    return day.weekday() in opening_weekdays and day not in closure_map


def count_open_days(start_date, end_date, opening_weekdays, closure_map):
    return len(get_open_dates(start_date, end_date, opening_weekdays, closure_map))


def group_dates_into_ranges(dates):
    """Regroupe une liste de dates en plages contiguës."""
    ordered = sorted(set(dates))
    ranges = []
    for day in ordered:
        if ranges and day == ranges[-1][1] + timedelta(days=1):
            ranges[-1] = (ranges[-1][0], day)
        else:
            ranges.append((day, day))
    return ranges


def format_weekdays(weekdays):
    """Libellé lisible : « lundi, mardi, ..., samedi »."""
    labels = [WEEKDAY_LABELS[day].lower() for day in weekdays if 0 <= day <= 6]
    if not labels:
        return "aucun jour"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " et " + labels[-1]


def closure_kind_labels():
    return dict(Closure.KIND_CHOICES)
