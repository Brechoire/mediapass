from django.core.cache import cache

from .models import Category, Reservation, Structure


def reservation_count(request):
    if not request.user.is_authenticated:
        return {"reservation_count": 0}
    count = cache.get_or_set(
        "reservation_count_pending",
        Reservation.objects.filter(is_approved=False).count(),
        300,
    )
    return {"reservation_count": count}


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
