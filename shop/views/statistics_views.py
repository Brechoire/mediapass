from calendar import month_name
from datetime import date, datetime
from statistics import mean, median

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractYear, TruncMonth
from django.shortcuts import render

from accounts.utils import is_staff_or_superuser
from ..models import Category, Product, Reservation, Structure


@user_passes_test(is_staff_or_superuser)
def statistics(request):
    current_year = datetime.now().year
    selected_year = request.GET.get("year")

    if selected_year:
        try:
            selected_year = int(selected_year)
        except (ValueError, TypeError):
            selected_year = current_year
    else:
        selected_year = current_year

    available_years = list(
        Reservation.objects.annotate(year=ExtractYear("start_date"))
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )

    if not available_years:
        available_years = [current_year]

    reservations = Reservation.objects.filter(start_date__year=selected_year)

    total_reservations = reservations.count()

    reservations_by_structure = Structure.objects.annotate(
        total_reservations=Count(
            "reservations",
            filter=Q(reservations__start_date__year=selected_year),
        )
    ).order_by("-total_reservations")

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

    monthly_average = round(total_reservations / 12, 1) if total_reservations else 0.0
    if reservations_by_month and max(reservations_by_month) > 0:
        monthly_max_value = max(reservations_by_month)
        monthly_max_index = reservations_by_month.index(monthly_max_value)
    else:
        monthly_max_value = 0
        monthly_max_index = -1

    top_structure = next(
        (s for s in reservations_by_structure if s.total_reservations), None
    )
    top_product = products_stats.first() if products_stats else None

    chart_structures = [
        {"name": s.name, "total": s.total_reservations}
        for s in reservations_by_structure
        if s.total_reservations
    ][:8]
    remaining_total = sum(
        s.total_reservations for s in reservations_by_structure if s.total_reservations
    ) - sum(s["total"] for s in chart_structures)
    has_more_structures = sum(
        1 for s in reservations_by_structure if s.total_reservations
    ) > len(chart_structures)
    if has_more_structures and remaining_total > 0:
        chart_structures.append({"name": "Autres", "total": remaining_total})

    # --- Phase A : pilotage des réservations (définitions alignées sur reservation_list) ---
    # En attente = ni approuvée, ni rejetée, sans motif de refus (cf. reservation_views.py).
    funnel_approved = reservations.filter(is_approved=True).count()
    funnel_pending = reservations.filter(
        is_approved=False, is_rejected=False, disapproval_reason__isnull=True
    ).count()
    funnel_rejected = reservations.filter(
        Q(is_rejected=True) | Q(disapproval_reason__isnull=False)
    ).count()
    funnel = {
        "approved": funnel_approved,
        "pending": funnel_pending,
        "rejected": funnel_rejected,
        "approval_rate": (
            round(funnel_approved / total_reservations * 100, 1)
            if total_reservations
            else 0.0
        ),
    }

    # Volumes empruntés (unités) + panier moyen.
    total_quantity = reservations.aggregate(total=Sum("quantity"))["total"] or 0
    avg_basket = (
        round(total_quantity / total_reservations, 1) if total_reservations else 0.0
    )

    # Mix par catégorie + stock dormant (produits jamais réservés sur l'année).
    categories_stats = (
        Category.objects.annotate(
            reservation_count=Count(
                "products__reservations",
                filter=Q(products__reservations__start_date__year=selected_year),
            ),
            total_quantity=Sum(
                "products__reservations__quantity",
                filter=Q(products__reservations__start_date__year=selected_year),
            ),
        )
        .filter(reservation_count__gt=0)
        .order_by("-reservation_count")
    )
    chart_categories = [
        {
            "name": c.name,
            "total": c.reservation_count,
            "quantity": c.total_quantity or 0,
        }
        for c in categories_stats
    ]
    dormant_products_qs = (
        Product.objects.annotate(
            reservation_count=Count(
                "reservations",
                filter=Q(reservations__start_date__year=selected_year),
            )
        )
        .filter(reservation_count=0)
        .order_by("name")
    )
    dormant_count = dormant_products_qs.count()
    dormant_sample = list(dormant_products_qs[:10])

    # Durées de prêt en jours (médiane robuste + moyenne + parts courts/longs).
    durations = [
        (r.end_date - r.start_date).total_seconds() / 86400
        for r in reservations.only("start_date", "end_date")
        if r.end_date and r.start_date and r.end_date >= r.start_date
    ]
    if durations:
        duration_stats = {
            "median": round(median(durations), 1),
            "mean": round(mean(durations), 1),
            "short_share": round(
                sum(1 for d in durations if d <= 3) / len(durations) * 100, 1
            ),
            "long_share": round(
                sum(1 for d in durations if d > 7) / len(durations) * 100, 1
            ),
            "count": len(durations),
        }
    else:
        duration_stats = None

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
        start_date__gte=start_date_selected_year, start_date__lte=end_date_selected_year
    )

    previous_year_reservations = Reservation.objects.filter(
        start_date__gte=start_date_previous_year, start_date__lte=end_date_previous_year
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
                (total_reservations_to_date - previous_year_data["total_reservations"])
                / previous_year_data["total_reservations"]
                * 100
            )
        else:
            previous_year_data["reservations_variation"] = 100

        previous_year_data["total_reservations_to_date"] = total_reservations_to_date

        structure_compare_qs = Structure.objects.annotate(
            current_year_count=Count(
                "reservations",
                filter=Q(
                    reservations__start_date__gte=start_date_selected_year,
                    reservations__start_date__lte=end_date_selected_year,
                ),
            ),
            previous_year_count=Count(
                "reservations",
                filter=Q(
                    reservations__start_date__gte=start_date_previous_year,
                    reservations__start_date__lte=end_date_previous_year,
                ),
            ),
        ).order_by("-current_year_count")

        structures_comparison = []
        for structure in structure_compare_qs:
            curr = structure.current_year_count
            prev = structure.previous_year_count
            if prev > 0:
                var = round((curr - prev) / prev * 100, 1)
            else:
                var = 100 if curr > 0 else 0

            structures_comparison.append(
                {
                    "structure": structure,
                    "current_year_reservations": curr,
                    "previous_year_reservations": prev,
                    "variation": var,
                }
            )

        previous_year_data["structures_comparison"] = structures_comparison

    context = {
        "reservations_by_month": reservations_by_month,
        "monthly_average": monthly_average,
        "monthly_max_index": monthly_max_index,
        "monthly_max_value": monthly_max_value,
        "current_year": selected_year,
        "selected_year": selected_year,
        "available_years": available_years,
        "reservations_by_structure": reservations_by_structure,
        "chart_structures": chart_structures,
        "products_stats": products_stats,
        "total_reservations": total_reservations,
        "top_structure": top_structure,
        "top_product": top_product,
        "funnel": funnel,
        "total_quantity": total_quantity,
        "avg_basket": avg_basket,
        "chart_categories": chart_categories,
        "dormant_count": dormant_count,
        "dormant_sample": dormant_sample,
        "duration_stats": duration_stats,
        "previous_year_data": previous_year_data,
    }

    return render(request, "shop/statistics.html", context)
