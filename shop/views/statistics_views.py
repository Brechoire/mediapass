from calendar import month_name
from datetime import date, datetime

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.db.models.functions import ExtractYear, TruncMonth
from django.shortcuts import render

from accounts.utils import is_staff_or_superuser
from ..models import Product, Reservation, Structure


@user_passes_test(is_staff_or_superuser)
def statistics(request):
    current_year = datetime.now().year
    selected_year = request.GET.get('year')

    if selected_year:
        try:
            selected_year = int(selected_year)
        except (ValueError, TypeError):
            selected_year = current_year
    else:
        selected_year = current_year

    available_years = list(
        Reservation.objects
        .annotate(year=ExtractYear('start_date'))
        .values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )

    if not available_years:
        available_years = [current_year]

    reservations = Reservation.objects.filter(start_date__year=selected_year)

    total_reservations = reservations.count()

    reservations_by_structure = Structure.objects.annotate(
        total_reservations=Count(
            'reservations',
            filter=Q(reservations__start_date__year=selected_year),
        )
    ).order_by('-total_reservations')

    products_stats = (
        Product.objects.select_related("category")
        .annotate(
            reservation_count=Count(
                "reservations",
                filter=Q(reservations__start_date__year=selected_year),
            )
        )
        .filter(reservation_count__gt=0)
        .order_by("-reservation_count")
    )

    monthly_raw = (
        reservations.annotate(month=TruncMonth("start_date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    monthly_map = {m["month"].month if m["month"] else 0: m for m in monthly_raw}
    reservations_by_month = []
    for m in range(1, 13):
        reservations_by_month.append(monthly_map.get(m, {}).get("count", 0))

    previous_year_data = None
    previous_year = selected_year - 1

    current_date_obj = datetime.now().date()

    if selected_year == current_year:
        end_date_selected_year = date(
            selected_year, current_date_obj.month, current_date_obj.day
        )
    else:
        end_date_selected_year = date(selected_year, 12, 31)

    start_date_selected_year = date(selected_year, 1, 1)
    start_date_previous_year = date(previous_year, 1, 1)

    if selected_year == current_year:
        end_date_previous_year = date(
            previous_year, current_date_obj.month, current_date_obj.day
        )
        period_str = (
            f"(1 jan - {current_date_obj.day} " f"{month_name[current_date_obj.month]})"
        )
    else:
        end_date_previous_year = date(previous_year, 12, 31)
        period_str = "(ann\u00e9e compl\u00e8te)"

    selected_year_reservations_to_date = Reservation.objects.filter(
        start_date__gte=start_date_selected_year,
        start_date__lte=end_date_selected_year
    )

    previous_year_reservations = Reservation.objects.filter(
        start_date__gte=start_date_previous_year,
        start_date__lte=end_date_previous_year
    )

    if previous_year_reservations.exists():
        total_reservations_to_date = selected_year_reservations_to_date.count()

        previous_year_data = {
            "year": previous_year,
            "total_reservations": previous_year_reservations.count(),
            "period": period_str,
        }

        if previous_year_data["total_reservations"] > 0:
            previous_year_data["reservations_variation"] = (
                (total_reservations_to_date -
                 previous_year_data["total_reservations"])
                / previous_year_data["total_reservations"]
                * 100
            )
        else:
            previous_year_data["reservations_variation"] = 100

        previous_year_data["total_reservations_to_date"] = (
            total_reservations_to_date
        )

        structure_compare_qs = Structure.objects.annotate(
            current_year_count=Count(
                'reservations',
                filter=Q(
                    reservations__start_date__gte=start_date_selected_year,
                    reservations__start_date__lte=end_date_selected_year,
                ),
            ),
            previous_year_count=Count(
                'reservations',
                filter=Q(
                    reservations__start_date__gte=start_date_previous_year,
                    reservations__start_date__lte=end_date_previous_year,
                ),
            ),
        ).order_by('-current_year_count')

        structures_comparison = []
        for structure in structure_compare_qs:
            curr = structure.current_year_count
            prev = structure.previous_year_count
            if prev > 0:
                var = round((curr - prev) / prev * 100, 1)
            else:
                var = 100 if curr > 0 else 0

            structures_comparison.append({
                "structure": structure,
                "current_year_reservations": curr,
                "previous_year_reservations": prev,
                "variation": var,
            })

        previous_year_data["structures_comparison"] = structures_comparison

    context = {
        "reservations_by_month": reservations_by_month,
        "current_year": selected_year,
        "selected_year": selected_year,
        "available_years": available_years,
        "reservations_by_structure": reservations_by_structure,
        "products_stats": products_stats,
        "total_reservations": total_reservations,
        "previous_year_data": previous_year_data,
    }

    return render(request, "shop/statistics.html", context)
