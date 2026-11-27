"""Calcul des occurrences d'une série d'ateliers.

La récurrence est volontairement simple : elle sert à créer plusieurs
ateliers indépendants en une seule saisie. Les occurrences ne sont pas
reliées par une contrainte forte, seulement par un identifiant de série.
"""

from datetime import timedelta

from dateutil.relativedelta import relativedelta

RECURRENCE_NONE = "none"
RECURRENCE_WEEKLY = "weekly"
RECURRENCE_BIWEEKLY = "biweekly"
RECURRENCE_MONTHLY = "monthly"

RECURRENCE_CHOICES = [
    (RECURRENCE_NONE, "Aucune répétition"),
    (RECURRENCE_WEEKLY, "Toutes les semaines"),
    (RECURRENCE_BIWEEKLY, "Toutes les 2 semaines"),
    (RECURRENCE_MONTHLY, "Tous les mois"),
]

MAX_RECURRENCE_COUNT = 24


def _offset(recurrence, index):
    """Décalage entre la première occurrence et l'occurrence ``index``."""
    if recurrence == RECURRENCE_WEEKLY:
        return timedelta(weeks=index)
    if recurrence == RECURRENCE_BIWEEKLY:
        return timedelta(weeks=2 * index)
    if recurrence == RECURRENCE_MONTHLY:
        return relativedelta(months=index)
    return timedelta(0)


def occurrence_dates(start_date, end_date, recurrence, count):
    """Retourne la liste des couples (date de début, date de fin).

    - ``recurrence`` vaut ``none`` : une seule occurrence.
    - ``count`` est borné entre 1 et ``MAX_RECURRENCE_COUNT``.
    - Pour un atelier sur plusieurs jours, la date de fin est décalée
      du même intervalle que la date de début.
    - Une récurrence mensuelle démarrée un 31 tombe sur le dernier jour
      des mois plus courts, puis revient au 31 le mois suivant.
    """
    if not start_date:
        return []

    if recurrence not in {
        RECURRENCE_WEEKLY,
        RECURRENCE_BIWEEKLY,
        RECURRENCE_MONTHLY,
    }:
        return [(start_date, end_date)]

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(count, MAX_RECURRENCE_COUNT))

    occurrences = []
    for index in range(count):
        offset = _offset(recurrence, index)
        occurrence_start = start_date + offset
        occurrence_end = end_date + offset if end_date else None
        occurrences.append((occurrence_start, occurrence_end))
    return occurrences
