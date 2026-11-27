"""Détection des conflits de lieu et de créneau entre ateliers."""

from .models import Workshop


def _date_label(workshop):
    """Libellé lisible de la période d'un atelier."""
    if workshop.date_end and workshop.date_end != workshop.date:
        return (
            f"du {workshop.date:%d/%m/%Y} au "
            f"{workshop.date_end:%d/%m/%Y}"
        )
    return f"le {workshop.date:%d/%m/%Y}"


def find_workshop_conflicts(workshop):
    """Retourne les ateliers en conflit avec le lieu et le créneau donnés.

    Un conflit existe si les deux ateliers partagent le même lieu, que
    leurs plages de dates se chevauchent et que leurs horaires se
    chevauchent également.
    """
    if not workshop.location_id or not workshop.date:
        return []

    end_date = workshop.date_end or workshop.date
    candidates = (
        Workshop.objects.filter(
            location_id=workshop.location_id,
            date__lte=end_date,
        )
        .exclude(pk=workshop.pk)
        .select_related("location")
        .order_by("date", "start_time")
    )

    conflicts = []
    for other in candidates:
        other_end = other.date_end or other.date
        if other_end < workshop.date:
            continue
        if not all(
            (
                workshop.start_time,
                workshop.end_time,
                other.start_time,
                other.end_time,
            )
        ):
            continue
        if (
            other.start_time < workshop.end_time
            and other.end_time > workshop.start_time
        ):
            conflicts.append(other)
    return conflicts


def conflict_message(conflicts):
    """Construit le message d'erreur d'un ou plusieurs conflits."""
    details = "; ".join(
        f"« {other.name} » {_date_label(other)} de "
        f"{other.start_time:%H:%M} à {other.end_time:%H:%M}"
        for other in conflicts
    )
    return (
        "Un atelier existe déjà sur ce lieu et ce créneau : "
        f"{details}."
    )
