from django.core.cache import cache

from .models import Category, Reservation, Structure


def reservation_count(request):
    if not request.user.is_authenticated:
        return {"reservation_count": 0, "pending_reservations_count": 0}
    # File d'attente globale (toutes années), même définition que reservation_list
    # et reservation_calendar : exclut approuvées, rejetées et motifs renseignés.
    # Requête directe sans cache : le count est indexé et le cache sans
    # invalidation affichait une pastille périmée après traitement.
    count = Reservation.objects.filter(
        is_approved=False, is_rejected=False, disapproval_reason__isnull=True
    ).count()
    return {"reservation_count": count, "pending_reservations_count": count}


def count_pending_structures(request):
    if not request.user.is_authenticated:
        return {"pending_count": 0}
    count = cache.get_or_set(
        "pending_structures_count",
        Structure.objects.filter(valid=False).count(),
        300,
    )
    return {"pending_count": count}


def category_list_context(request):
    category_list = cache.get_or_set(
        "category_list_all",
        Category.objects.all(),
        3600,
    )
    return {"category_list": category_list}
