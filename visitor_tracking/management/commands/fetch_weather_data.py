from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from visitor_tracking.services import WeatherService


class Command(BaseCommand):
    help = "Récupère les données météo depuis Open-Meteo pour une période donnée."

    def add_arguments(self, parser):
        parser.add_argument("--start", type=str, help="Date de début (YYYY-MM-DD)")
        parser.add_argument("--end", type=str, help="Date de fin (YYYY-MM-DD)")

    def handle(self, *args, **options):
        today = timezone.now().date()

        if options["start"]:
            start = date.fromisoformat(options["start"])
        else:
            start = today - timedelta(days=30)

        if options["end"]:
            end = date.fromisoformat(options["end"])
        else:
            end = today

        self.stdout.write(f"Récupération des données météo du {start} au {end}...")
        WeatherService.fetch_range(start, end)
        self.stdout.write(self.style.SUCCESS("Terminé."))
