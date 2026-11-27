"""Normalise les noms d'ateliers existants vers la liste canonique."""

from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from workshop.models import Workshop, WorkshopName
from workshop.naming import choose_canonical_name, normalize_workshop_name


class Command(BaseCommand):
    help = (
        "Affiche ou applique les renommages des ateliers vers les noms "
        "canoniques de la liste. Sans --apply, la commande est un diagnostic."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Applique les créations et renommages (par défaut : dry-run).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        counts = Counter(Workshop.objects.values_list("name", flat=True))
        groups = defaultdict(dict)
        ignored = []

        for raw_name, count in counts.items():
            display = " ".join(str(raw_name or "").split())
            key = normalize_workshop_name(display)
            if not key:
                ignored.append(raw_name)
                continue
            groups[key][display] = groups[key].get(display, 0) + count

        catalog = {entry.normalized: entry.name for entry in WorkshopName.objects.all()}
        missing = []
        renames = []

        for key, display_counts in groups.items():
            variants = list(display_counts.items())
            target = catalog.get(key)
            if target is None:
                target = choose_canonical_name(variants)
                missing.append((target, key))
            for name, count in variants:
                if name != target:
                    renames.append((name, target, count))

        if ignored:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(ignored)} nom(s) ignoré(s) car vide(s) ou sans "
                    "lettre/chiffre."
                )
            )

        if not missing and not renames:
            self.stdout.write(
                self.style.SUCCESS(
                    "Tous les noms d'ateliers sont déjà alignés sur la liste."
                )
            )
            return

        if missing:
            self.stdout.write("Entrées manquantes dans la liste :")
            for name, key in sorted(missing, key=lambda item: item[0].casefold()):
                self.stdout.write(f"  + {name}  [clé : {key}]")

        if renames:
            self.stdout.write("Renommages prévus :")
            for old, new, count in sorted(
                renames, key=lambda item: (item[0].casefold(), item[0])
            ):
                plural = "atelier" if count == 1 else "ateliers"
                self.stdout.write(f"  - {old} -> {new}  ({count} {plural})")

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "Mode diagnostic : aucune modification. "
                    "Relancez avec --apply pour appliquer."
                )
            )
            return

        with transaction.atomic():
            for name, key in missing:
                WorkshopName.objects.get_or_create(
                    normalized=key,
                    defaults={"name": name},
                )
            for old, new, _count in renames:
                Workshop.objects.filter(name=old).update(name=new)

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé : {len(missing)} entrée(s) ajoutée(s), "
                f"{sum(count for _old, _new, count in renames)} atelier(s) "
                "renommé(s)."
            )
        )
