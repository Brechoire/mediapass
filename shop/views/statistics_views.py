from calendar import month_name
from datetime import date, datetime
from statistics import mean, median

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear, TruncMonth
from django.shortcuts import render

from accounts.utils import is_staff_or_superuser
from ..models import Category, Product, Reservation, Structure


# Seuils d'affichage du badge de taux d'approbation (cosmétique, non métier).
APPROVAL_RATE_HIGH = 80
APPROVAL_RATE_MEDIUM = 50

# Produits affichés d'emblée ; le reste est dépliable (poids du DOM).
PRODUCTS_INITIAL_LIMIT = 100

MONTH_NAMES_FR = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def _plural(n, singular, plural=None):
    """Accord simple pour la synthèse."""
    if n == 1:
        return singular
    return plural or singular + "s"


def _variation_wording(variation):
    """Formulation naturelle d'une variation en % (ou stable)."""
    try:
        v = float(variation)
    except (TypeError, ValueError):
        return None
    if v > 0.5:
        return f"en hausse de {v:.1f} %"
    if v < -0.5:
        return f"en baisse de {abs(v):.1f} %"
    return "stables"


def build_synthese(data):
    """Construit la synthèse narrative (~10 lignes, ton naturel).

    Args:
        data (dict): year, total, units, structures_count, products_count,
            approval_rate, approved, pending, rejected, refusal_top (tuple
            label/count|None), previous (dict|None avec year,
            reservations_variation), top_structure (tuple nom/count|None),
            top_product (tuple nom/count|None), peak_month (tuple label/count|None),
            median_duration (float|None), mean_duration (float|None),
            dormant_count, inactive_count, perimetre (str|None).

    Returns:
        dict: {"perimetre": str|None, "phrases": list[str]}.
    """
    phrases = []

    year = data.get("year", "")
    total = data.get("total", 0) or 0
    units = data.get("units", 0) or 0
    phrases.append(
        f"En {year}, {total} {_plural(total, 'réservation')} "
        f"ont été enregistrées, mobilisant {units} {_plural(units, 'unité')} de matériel."
    )

    structures_count = data.get("structures_count", 0) or 0
    products_count = data.get("products_count", 0) or 0
    phrases.append(
        f"Elles proviennent de {structures_count} "
        f"{_plural(structures_count, 'structure')} et concernent "
        f"{products_count} {_plural(products_count, 'produit')} différents."
    )

    phrases.append(
        f"Le taux d'approbation s'élève à {data.get('approval_rate', 0) or 0:.1f} % "
        f"({data.get('approved', 0) or 0} approuvées, "
        f"{data.get('pending', 0) or 0} en attente, "
        f"{data.get('rejected', 0) or 0} refusées)."
    )

    refusal_top = data.get("refusal_top")
    if refusal_top and refusal_top[1]:
        phrases.append(
            f"Les refus concernent surtout « {refusal_top[0]} » "
            f"({refusal_top[1]} {_plural(refusal_top[1], 'cas')})."
        )

    previous = data.get("previous")
    if previous:
        w_word = _variation_wording(previous.get("reservations_variation"))
        phrases.append(
            f"Par rapport à {previous.get('year')} sur la même période, "
            f"les réservations sont {w_word}."
        )

    top_structure = data.get("top_structure")
    top_product = data.get("top_product")
    if top_structure and top_product:
        phrases.append(
            f"La structure la plus active est {top_structure[0]} "
            f"({top_structure[1]} {_plural(top_structure[1], 'réservation')}) "
            f"et la ressource la plus demandée est {top_product[0]} "
            f"({top_product[1]} {_plural(top_product[1], 'réservation')})."
        )

    peak_month = data.get("peak_month")
    if peak_month:
        phrases.append(
            f"Le mois le plus actif est {peak_month[0]} "
            f"({peak_month[1]} {_plural(peak_month[1], 'réservation')})."
        )

    median_duration = data.get("median_duration")
    if median_duration is not None:
        phrases.append(
            f"La durée médiane d'un prêt est de {median_duration:.1f} jours "
            f"(moyenne {data.get('mean_duration', 0) or 0:.1f})."
        )

    coverage_parts = []
    dormant = data.get("dormant_count", 0) or 0
    if dormant:
        coverage_parts.append(
            f"{dormant} {_plural(dormant, 'produit')} jamais réservé{_plural(dormant, '', 's')}"
        )
    inactive = data.get("inactive_count", 0) or 0
    if inactive:
        coverage_parts.append(
            f"{inactive} {_plural(inactive, 'structure')} sans réservation"
        )
    if coverage_parts:
        phrases.append("Côté couverture : " + " ; ".join(coverage_parts) + ".")
    else:
        phrases.append(
            "Tous les produits et toutes les structures ont connu "
            "au moins une réservation."
        )

    pending = data.get("pending", 0) or 0
    if pending:
        phrases.append(
            f"Avec {pending} {_plural(pending, 'demande')} en attente, "
            f"leur traitement reste la priorité."
        )
    else:
        phrases.append("Aucune demande en attente : le flux de validation est à jour.")

    return {"perimetre": data.get("perimetre"), "phrases": phrases}


def _parse_optional_id(value, model):
    """Parse un id passé en GET ; None si absent/invalide/inexistant (pas de 500)."""
    try:
        pk = int(value)
    except (TypeError, ValueError):
        return None
    return pk if model.objects.filter(pk=pk).exists() else None


@user_passes_test(is_staff_or_superuser)
def statistics(request):
    current_year = datetime.now().year
    raw_year = request.GET.get("year", current_year)

    try:
        selected_year = int(raw_year)
    except (ValueError, TypeError):
        selected_year = current_year
        messages.warning(request, "Année invalide, affichage de l'année en cours.")

    available_years = list(
        Reservation.objects.annotate(year=ExtractYear("start_date"))
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )

    if not available_years:
        available_years = [current_year]

    previous_year = selected_year - 1

    structure_id = _parse_optional_id(request.GET.get("structure"), Structure)
    category_id = _parse_optional_id(request.GET.get("category"), Category)

    year_qs = Reservation.objects.filter(start_date__year=selected_year)

    # Filtres combinés (ET) pour les indicateurs.
    reservations = year_qs
    if structure_id:
        reservations = reservations.filter(structure_id=structure_id)
    if category_id:
        reservations = reservations.filter(product__category_id=category_id)

    # Bases croisées : chaque ventilation ignore son propre filtre
    # pour garder le contexte quand il est actif (drill-down).
    struct_qs = year_qs
    if category_id:
        struct_qs = struct_qs.filter(product__category_id=category_id)
    cat_qs = year_qs
    if structure_id:
        cat_qs = cat_qs.filter(structure_id=structure_id)

    # Bornes de période (année sélectionnée + N-1 à date égale).
    current_date_obj = datetime.now().date()
    if selected_year == current_year:
        end_date_selected_year = date(
            selected_year, current_date_obj.month, current_date_obj.day
        )
        end_date_previous_year = date(
            previous_year, current_date_obj.month, current_date_obj.day
        )
        period_str = (
            f"(1 jan - {current_date_obj.day} " f"{month_name[current_date_obj.month]})"
        )
    else:
        end_date_selected_year = date(selected_year, 12, 31)
        end_date_previous_year = date(previous_year, 12, 31)
        period_str = "(ann\u00e9e compl\u00e8te)"
    start_date_selected_year = date(selected_year, 1, 1)
    start_date_previous_year = date(previous_year, 1, 1)

    # Miroir N-1 de cat_qs (même périmètre structure, année précédente).
    prev_cat_qs = Reservation.objects.filter(
        start_date__gte=start_date_previous_year, start_date__lte=end_date_previous_year
    )
    if structure_id:
        prev_cat_qs = prev_cat_qs.filter(structure_id=structure_id)

    total_reservations = reservations.count()

    structures_list = list(
        Structure.objects.annotate(
            total_reservations=Count(
                "reservations",
                filter=Q(reservations__in=struct_qs),
            )
        ).order_by("-total_reservations")
    )

    products_base = Product.objects.select_related("category")
    if category_id:
        products_base = products_base.filter(category_id=category_id)
    products_stats = (
        products_base.annotate(
            reservation_count=Count(
                "reservations",
                filter=Q(reservations__in=cat_qs),
            ),
            total_units=Coalesce(
                Sum("reservations__quantity", filter=Q(reservations__in=cat_qs)), 0
            ),
            prev_count=Count(
                "reservations",
                filter=Q(reservations__in=prev_cat_qs),
            ),
        )
        .filter(reservation_count__gt=0)
        .order_by("-reservation_count")
    )

    # Évaluation unique : attributs dérivés (ratio, tendance, alerte stock).
    evaluated_products = list(products_stats)
    for p in evaluated_products:
        stock = p.quantity or 0
        units = p.total_units or 0
        p.rotation_ratio = round(units / stock * 100, 1) if stock else None
        p.rotation_ratio_capped = (
            min(p.rotation_ratio, 100) if p.rotation_ratio is not None else 0
        )
        p.trend_delta = (p.reservation_count or 0) - (p.prev_count or 0)
        if stock == 0:
            p.stock_alert = "rupture" if units else "sans-stock"
        elif p.rotation_ratio >= 100:
            p.stock_alert = "tension"
        else:
            p.stock_alert = None
    products_max_count = (
        evaluated_products[0].reservation_count if evaluated_products else 0
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

    # Moyenne rapportée aux mois écoulés pour l'année en cours (pas /12 toute l'année).
    if selected_year == current_year:
        average_months = max(current_date_obj.month, 1)
    else:
        average_months = 12
    monthly_average = round(total_reservations / average_months, 1) if total_reservations else 0.0

    if reservations_by_month and max(reservations_by_month) > 0:
        monthly_max_value = max(reservations_by_month)
        monthly_max_index = reservations_by_month.index(monthly_max_value)
        monthly_max_label = MONTH_NAMES_FR[monthly_max_index]
    else:
        monthly_max_value = 0
        monthly_max_index = -1
        monthly_max_label = None

    monthly_rows = [
        {"month": m, "label": MONTH_NAMES_FR[m - 1], "count": c}
        for m, c in enumerate(reservations_by_month, start=1)
    ]

    top_structure = next((s for s in structures_list if s.total_reservations), None)
    top_product = evaluated_products[0] if evaluated_products else None

    chart_structures = [
        {"name": s.name, "total": s.total_reservations}
        for s in structures_list
        if s.total_reservations
    ][:8]
    remaining_total = sum(
        s.total_reservations for s in structures_list if s.total_reservations
    ) - sum(s["total"] for s in chart_structures)
    has_more_structures = sum(
        1 for s in structures_list if s.total_reservations
    ) > len(chart_structures)
    if has_more_structures and remaining_total > 0:
        chart_structures.append({"name": "Autres", "total": remaining_total})

    inactive_structures = [s for s in structures_list if not s.total_reservations]

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

    # Volumes empruntés (unités) + panier moyen + valeur mobilisée.
    total_quantity = reservations.aggregate(total=Sum("quantity"))["total"] or 0
    avg_basket = (
        round(total_quantity / total_reservations, 1) if total_reservations else 0.0
    )
    stock_value = (
        reservations.aggregate(
            value=Sum(
                ExpressionWrapper(
                    F("product__price") * F("quantity"),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            )
        )["value"]
        or 0
    )

    # Motifs de refus (définitions alignées sur reservation_list).
    refusal_counts = {
        r["disapproval_reason"]: r["count"]
        for r in reservations.exclude(disapproval_reason__isnull=True)
        .exclude(disapproval_reason="")
        .values("disapproval_reason")
        .annotate(count=Count("id"))
    }
    refusal_stats = [
        {"code": code, "label": label, "count": refusal_counts.get(code, 0)}
        for code, label in Reservation.DISAPPROVAL_REASONS
    ]

    # Mix par catégorie + stock dormant (produits jamais réservés sur le périmètre filtré).
    categories_stats = (
        Category.objects.annotate(
            reservation_count=Count(
                "products__reservations",
                filter=Q(products__reservations__in=cat_qs),
            ),
            total_quantity=Sum(
                "products__reservations__quantity",
                filter=Q(products__reservations__in=cat_qs),
            ),
        )
        .filter(reservation_count__gt=0)
        .order_by("-reservation_count")
    )
    chart_categories = [
        {
            "id": c.pk,
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
                filter=Q(reservations__in=cat_qs),
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

    # Le comparatif N-1 respecte les mêmes filtres structure/catégorie.
    previous_year_reservations = Reservation.objects.filter(
        start_date__gte=start_date_previous_year, start_date__lte=end_date_previous_year
    )
    if structure_id:
        previous_year_reservations = previous_year_reservations.filter(
            structure_id=structure_id
        )
    if category_id:
        previous_year_reservations = previous_year_reservations.filter(
            product__category_id=category_id
        )

    selected_year_reservations_to_date = reservations.filter(
        start_date__gte=start_date_selected_year, start_date__lte=end_date_selected_year
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

        category_range_filter = (
            Q(reservations__product__category_id=category_id)
            if category_id
            else Q()
        )
        structure_compare_qs = Structure.objects.annotate(
            current_year_count=Count(
                "reservations",
                filter=(
                    Q(
                        reservations__start_date__gte=start_date_selected_year,
                        reservations__start_date__lte=end_date_selected_year,
                    )
                    & category_range_filter
                ),
            ),
            previous_year_count=Count(
                "reservations",
                filter=(
                    Q(
                        reservations__start_date__gte=start_date_previous_year,
                        reservations__start_date__lte=end_date_previous_year,
                    )
                    & category_range_filter
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

    # Taux d'approbation par structure (périmètre filtré, triés par taux croissant).
    approval_rows = list(
        Structure.objects.annotate(
            approval_total=Count("reservations", filter=Q(reservations__in=struct_qs)),
            approval_approved=Count(
                "reservations",
                filter=Q(reservations__in=struct_qs) & Q(reservations__is_approved=True),
            ),
        ).filter(approval_total__gt=0)
    )
    for s in approval_rows:
        s.approval_rate = (
            round(s.approval_approved / s.approval_total * 100, 1)
            if s.approval_total
            else 0.0
        )
    approval_by_structure = sorted(approval_rows, key=lambda s: s.approval_rate)[:8]

    # Matrice catégorie x mois (top 6 catégories, périmètre structure conservé).
    top_category_ids = [c["id"] for c in chart_categories[:6]]
    category_month_matrix = {"categories": [], "matrix": []}
    if top_category_ids:
        cat_month_detail = (
            struct_qs.filter(product__category__in=top_category_ids)
            .annotate(month=ExtractMonth("start_date"))
            .values("product__category__id", "product__category__name", "month")
            .annotate(count=Count("id"))
        )
        cat_names = {
            c["id"]: c["name"] for c in chart_categories if c["id"] in top_category_ids
        }
        grid = {
            (cid, m): 0 for cid in top_category_ids for m in range(1, 13)
        }
        for row in cat_month_detail:
            if row["month"] and (row["product__category__id"], row["month"]) in grid:
                grid[(row["product__category__id"], row["month"])] = row["count"]
        category_month_matrix = {
            "categories": [cat_names[cid] for cid in top_category_ids],
            "matrix": [
                {
                    "category": cat_names[cid],
                    "category_id": cid,
                    "months": [grid[(cid, m)] for m in range(1, 13)],
                    "total": sum(grid[(cid, m)] for m in range(1, 13)),
                }
                for cid in top_category_ids
            ],
        }

    active_structure = (
        Structure.objects.filter(pk=structure_id).first() if structure_id else None
    )
    active_category = (
        Category.objects.filter(pk=category_id).first() if category_id else None
    )

    # Synthèse narrative (~10 lignes, ton naturel), affichée en fin de page.
    refusal_top = None
    if refusal_counts:
        top_code = max(refusal_counts, key=lambda k: refusal_counts[k])
        if refusal_counts[top_code]:
            top_label = dict(Reservation.DISAPPROVAL_REASONS).get(top_code, top_code)
            refusal_top = (top_label, refusal_counts[top_code])
    perimetre_parts = []
    if active_structure:
        perimetre_parts.append(f"structure {active_structure.name}")
    if active_category:
        perimetre_parts.append(f"catégorie {active_category.name}")
    synthese = build_synthese(
        {
            "year": selected_year,
            "total": total_reservations,
            "units": total_quantity,
            "structures_count": sum(
                1 for s in structures_list if s.total_reservations
            ),
            "products_count": len(evaluated_products),
            "approval_rate": funnel["approval_rate"],
            "approved": funnel["approved"],
            "pending": funnel["pending"],
            "rejected": funnel["rejected"],
            "refusal_top": refusal_top,
            "previous": previous_year_data,
            "top_structure": (
                (top_structure.name, top_structure.total_reservations)
                if top_structure
                else None
            ),
            "top_product": (
                (top_product.name, top_product.reservation_count)
                if top_product
                else None
            ),
            "peak_month": (
                (monthly_max_label, monthly_max_value)
                if monthly_max_label
                else None
            ),
            "median_duration": duration_stats["median"] if duration_stats else None,
            "mean_duration": duration_stats["mean"] if duration_stats else None,
            "dormant_count": dormant_count,
            "inactive_count": len(inactive_structures),
            "perimetre": ", ".join(perimetre_parts) or None,
        }
    )

    context = {
        "reservations_by_month": reservations_by_month,
        "monthly_rows": monthly_rows,
        "monthly_average": monthly_average,
        "average_months": average_months,
        "monthly_max_index": monthly_max_index,
        "monthly_max_value": monthly_max_value,
        "monthly_max_label": monthly_max_label,
        "current_year": selected_year,
        "selected_year": selected_year,
        "available_years": available_years,
        "structure_id": structure_id,
        "category_id": category_id,
        "active_structure_name": active_structure.name if active_structure else "",
        "active_category_name": active_category.name if active_category else "",
        "has_active_filters": bool(structure_id or category_id),
        "all_structures": Structure.objects.order_by("name"),
        "all_categories": Category.objects.order_by("name"),
        "reservations_by_structure": structures_list,
        "chart_structures": chart_structures,
        "products_stats": products_stats,
        "products_initial_limit": PRODUCTS_INITIAL_LIMIT,
        "products_max_count": products_max_count,
        "total_reservations": total_reservations,
        "top_structure": top_structure,
        "top_product": top_product,
        "funnel": funnel,
        "refusal_stats": refusal_stats,
        "total_quantity": total_quantity,
        "avg_basket": avg_basket,
        "stock_value": stock_value,
        "chart_categories": chart_categories,
        "category_month_matrix": category_month_matrix,
        "approval_by_structure": approval_by_structure,
        "dormant_count": dormant_count,
        "dormant_sample": dormant_sample,
        "inactive_structures": inactive_structures,
        "duration_stats": duration_stats,
        "previous_year_data": previous_year_data,
        "approval_rate_high": APPROVAL_RATE_HIGH,
        "approval_rate_medium": APPROVAL_RATE_MEDIUM,
        "synthese": synthese,
    }

    return render(request, "shop/statistics.html", context)
