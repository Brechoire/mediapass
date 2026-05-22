"""Middleware for tracking page visits."""

import logging
from datetime import timedelta

from django.utils import timezone
from user_agents import parse

from .models import PageVisit


class AnalyticsMiddleware:
    """Middleware for automatically tracking page visits."""

    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response

    def __call__(self, request):
        """Process the request and log the visit."""
        # Liste des bots à ignorer
        IGNORED_BOTS = [
            "archive.org_bot",
            "Go-http-client",
            "bot",
            "spider",
            "crawler",
            "Googlebot",
            "Bingbot",
            "YandexBot",
        ]

        # Stocker le timestamp d'entrée
        request.visit_start_time = timezone.now()

        response = self.get_response(request)

        # Ne pas enregistrer les requêtes pour les fichiers statiques ou admin
        static_paths = ["/static/", "/media/", "/mediapassadmin/"]

        # Vérifier si le user agent correspond à un bot
        user_agent_string = request.META.get("HTTP_USER_AGENT", "").lower()
        is_bot = any(bot.lower() in user_agent_string for bot in IGNORED_BOTS)

        if (
            not any(path in request.path for path in static_paths)
            and not is_bot
        ):
            ip_address = self.get_client_ip(request)

            # Vérifier les visites récentes (30 dernières secondes)
            recent_visit = PageVisit.objects.filter(
                ip_address=ip_address,
                url=request.path,
                timestamp__gte=timezone.now() - timedelta(seconds=30),
            ).first()

            if not recent_visit:
                # Analyser le user agent (avec fallback si erreur)
                device_type = "desktop"
                try:
                    user_agent = parse(user_agent_string)
                    if user_agent.is_tablet:
                        device_type = "tablet"
                    elif user_agent.is_mobile:
                        device_type = "mobile"
                except Exception:
                    logger = logging.getLogger(__name__)
                    logger.warning("Erreur parsing user-agent: %s", user_agent_string[:100])

                # Calculer le temps passé
                time_spent = 0
                if hasattr(request, "visit_start_time"):
                    delta = timezone.now() - request.visit_start_time
                    time_spent = int(delta.total_seconds())

                # Créer l'entrée de visite
                PageVisit.objects.create(
                    url=request.path,
                    user=(
                        request.user if request.user.is_authenticated else None
                    ),
                    ip_address=ip_address,
                    user_agent=user_agent_string,
                    referrer=request.META.get("HTTP_REFERER", ""),
                    device_type=device_type,
                    time_spent=time_spent,
                    is_bounce=True,
                )

        return response

    def get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
