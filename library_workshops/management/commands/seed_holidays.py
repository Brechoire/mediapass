"""Commande d'import des vacances scolaires Zone B 2026/2027"""
from datetime import date
from django.core.management.base import BaseCommand
from library_workshops.models import SchoolHoliday

HOLIDAYS = [
    # Zone B 2025-2026
    {"name": "Vacances de Noël 2025", "start": date(2025, 12, 20), "end": date(2026, 1, 4)},
    {"name": "Vacances d'Hiver 2026", "start": date(2026, 2, 7), "end": date(2026, 2, 22)},
    {"name": "Vacances de Printemps 2026", "start": date(2026, 4, 11), "end": date(2026, 4, 26)},
    {"name": "Vacances d'Été 2026", "start": date(2026, 7, 4), "end": date(2026, 9, 1)},
    {"name": "Vacances de Toussaint 2026", "start": date(2026, 10, 17), "end": date(2026, 11, 2)},
    {"name": "Vacances de Noël 2026", "start": date(2026, 12, 19), "end": date(2027, 1, 3)},
    # Zone B 2026-2027
    {"name": "Vacances d'Hiver 2027", "start": date(2027, 2, 6), "end": date(2027, 2, 21)},
    {"name": "Vacances de Printemps 2027", "start": date(2027, 4, 10), "end": date(2027, 4, 25)},
]

ZONE = "B"


class Command(BaseCommand):
    help = "Importe les vacances scolaires Zone B en base"

    def handle(self, *args, **options):
        created = 0
        existing = 0
        for h in HOLIDAYS:
            obj, was = SchoolHoliday.objects.get_or_create(
                name=h["name"], zone=ZONE,
                defaults={"start_date": h["start"], "end_date": h["end"]},
            )
            if was:
                created += 1
            else:
                existing += 1
        self.stdout.write(self.style.SUCCESS(f"{created} vacances créées, {existing} existantes"))
