"""Views for displaying analytics data."""

import json
import logging
from datetime import datetime, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from user_agents import parse

from .models import PageVisit

logger = logging.getLogger(__name__)


@staff_member_required
def dashboard(request):
    """Display analytics dashboard."""
    # Récupération des dates depuis les paramètres GET
    try:
        start_date = datetime.strptime(
            request.GET.get("start_date", ""), "%Y-%m-%d"
        )
    except (ValueError, TypeError):
        start_date = timezone.now() - timedelta(days=30)

    try:
        end_date = datetime.strptime(
            request.GET.get("end_date", ""), "%Y-%m-%d"
        )
        # Ajouter 23:59:59 pour inclure toute la journée
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except (ValueError, TypeError):
        end_date = timezone.now()

    # Filtrer les visites sur la période
    visits = PageVisit.objects.filter(timestamp__range=(start_date, end_date))

    # Log pour déboguer
    logger.info(f"Période sélectionnée: du {start_date} au {end_date}")
    logger.info(f"Nombre total de visites: {visits.count()}")

    # Statistiques générales (1 seule requête au lieu de 4)
    general_stats = visits.aggregate(
        total=Count("id"),
        unique=Count("ip_address", distinct=True),
        avg_time_spent=Avg("time_spent"),
        bounce_count=Count("id", filter=Q(is_bounce=True)),
    )
    total_visits = general_stats["total"]
    unique_visitors = general_stats["unique"]
    avg_time_spent = general_stats["avg_time_spent"] or 0
    bounce_rate = (
        general_stats["bounce_count"] / total_visits * 100
        if total_visits > 0
        else 0
    )

    # Distribution des appareils
    device_stats = list(
        visits.values("device_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    logger.info(f"Statistiques des appareils: {device_stats}")

    # Analyse des user agents pour les navigateurs et OS
    # Limité aux 1000 dernières visites pour éviter l'explosion mémoire
    browser_counts = {}
    os_counts = {}

    for visit in visits.order_by('-timestamp')[:1000].iterator():
        if visit.user_agent:
            try:
                user_agent = parse(visit.user_agent)

                browser = user_agent.browser.family
                browser_counts[browser] = browser_counts.get(browser, 0) + 1

                os = user_agent.os.family
                os_counts[os] = os_counts.get(os, 0) + 1
            except Exception as e:
                logger.error(f"Erreur lors du parsing du user agent: {str(e)}")
                continue

    # Conversion en liste triée pour les graphiques
    browser_stats = [
        {"browser": k, "count": v}
        for k, v in sorted(
            browser_counts.items(), key=lambda x: x[1], reverse=True
        )
    ]
    os_stats = [
        {"os": k, "count": v}
        for k, v in sorted(os_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    logger.info(f"Statistiques des navigateurs: {browser_stats}")
    logger.info(f"Statistiques des OS: {os_stats}")

    # Pages les plus visitées
    top_pages = (
        visits.values("url")
        .annotate(visits=Count("id"), avg_time=Avg("time_spent"))
        .order_by("-visits")[:10]
    )

    # Visites quotidiennes
    daily_visits = list(
        visits.annotate(date=TruncDate("timestamp"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    logger.info(f"Visites quotidiennes: {daily_visits}")

    # Calcul de la croissance
    previous_period_length = (end_date - start_date).days
    previous_period_start = start_date - timedelta(days=previous_period_length)
    previous_period_end = start_date - timedelta(seconds=1)

    previous_visits = PageVisit.objects.filter(
        timestamp__range=(previous_period_start, previous_period_end)
    ).count()

    growth = (
        ((total_visits - previous_visits) / previous_visits * 100)
        if previous_visits > 0
        else 0
    )

    # Préparation des données pour les graphiques avec des valeurs par défaut
    device_data = {
        "labels": (
            [item["device_type"] for item in device_stats]
            if device_stats
            else ["Aucune donnée"]
        ),
        "data": (
            [item["count"] for item in device_stats] if device_stats else [0]
        ),
    }

    browser_data = {
        "labels": (
            [item["browser"] for item in browser_stats]
            if browser_stats
            else ["Aucune donnée"]
        ),
        "data": (
            [item["count"] for item in browser_stats] if browser_stats else [0]
        ),
    }

    os_data = {
        "labels": (
            [item["os"] for item in os_stats]
            if os_stats
            else ["Aucune donnée"]
        ),
        "data": [item["count"] for item in os_stats] if os_stats else [0],
    }

    daily_chart_data = {
        "labels": (
            [visit["date"].strftime("%d/%m") for visit in daily_visits]
            if daily_visits
            else ["Aucune donnée"]
        ),
        "data": (
            [visit["count"] for visit in daily_visits] if daily_visits else [0]
        ),
    }

    # Log des données des graphiques
    logger.info("Données des graphiques:")
    logger.info(f"Device data: {json.dumps(device_data)}")
    logger.info(f"Browser data: {json.dumps(browser_data)}")
    logger.info(f"OS data: {json.dumps(os_data)}")
    logger.info(f"Daily chart data: {json.dumps(daily_chart_data)}")

    context = {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "avg_time_spent": round(avg_time_spent, 1),
        "bounce_rate": round(bounce_rate, 1),
        "device_stats": device_stats,
        "browser_stats": browser_stats,
        "os_stats": os_stats,
        "top_pages": top_pages,
        "daily_visits": daily_visits,
        "growth": round(growth, 1),
        "start_date": start_date.date(),
        "end_date": end_date.date(),
        # Données JSON pour les graphiques
        "device_chart_data": json.dumps(device_data),
        "browser_chart_data": json.dumps(browser_data),
        "os_chart_data": json.dumps(os_data),
        "daily_chart_data": json.dumps(daily_chart_data),
    }

    return render(request, "analytics/dashboard.html", context)
