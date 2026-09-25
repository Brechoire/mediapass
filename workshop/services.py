"""Services pour la gestion des ateliers.

Ce module fournit des fonctions utilitaires pour la gestion des ateliers,
notamment le traitement des images et l'envoi de notifications.
"""

import random
import re
import string
import unicodedata
from os.path import splitext

from django.db import models
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce


def clean_filename(filename):
    """Nettoie le nom de fichier en remplaçant les caractères spéciaux.

    Args:
        filename (str): Le nom de fichier à nettoyer.

    Returns:
        str: Le nom de fichier nettoyé.
    """
    # Normaliser les caractères Unicode (décomposer les accents)
    filename = unicodedata.normalize("NFKD", filename)
    # Encoder en ASCII en ignorant les caractères non-ASCII
    filename = filename.encode("ASCII", "ignore").decode("ASCII")
    # Remplacer les caractères non-alphanumériques par des tirets
    filename = re.sub(r"[^a-zA-Z0-9.]", "-", filename)
    return filename


def generate_random_filename(filename):
    """Générer un nom de fichier aléatoire.

    Cette fonction prend un nom de fichier en entrée et génère un nouveau
    nom aléatoire tout en conservant l'extension du fichier d'origine.
    Cela évite les collisions de noms lors du téléchargement.

    Args:
        filename (str): Le nom d'origine du fichier.

    Returns:
        str: Un nom de fichier aléatoire avec l'extension d'origine.
    """
    try:
        # Nettoyer le nom de fichier
        clean_name = clean_filename(filename)

        # Séparer le nom et l'extension du fichier
        name, extension = splitext(clean_name)

        # Si l'extension est vide ou invalide, extraire depuis le nom original
        if not extension:
            _, extension = splitext(filename)

        # S'assurer que l'extension est en minuscules
        extension = extension.lower()

        # Générer une chaîne aléatoire de 10 caractères
        random_string = "".join(
            random.choice(string.ascii_lowercase) for i in range(10)
        )

        # Combiner la chaîne aléatoire avec l'extension
        new_filename = f"{random_string}{extension}"

        return new_filename
    except Exception as e:
        # En cas d'erreur, retourner un nom par défaut
        return f"image_{random.randint(1000, 9999)}.jpg"


CACHE_TIMEOUT = 300

ATTENDANCE_TRANCHES = [
    ("0", 0, 0),
    ("1-5", 1, 5),
    ("6-10", 6, 10),
    ("11-20", 11, 20),
    ("21+", 21, None),
]

MIN_ATELIERS_TOP_FLOP = 3


def get_stats_cache_key(year, location_id=None, city="", class_welcome=""):
    """Construit la clé de cache pour les stats ateliers."""
    key_city = city or "-"
    key_class = class_welcome or "-"
    return f"workshop_stats:{year}:{location_id or 0}:{key_city}:{key_class}:v1"


def apply_stats_filters(queryset, location_id=None, city="", class_welcome=""):
    """Applique les filtres lieu / ville / type sur un queryset Workshop."""
    if location_id:
        queryset = queryset.filter(location_id=location_id)
    if city:
        queryset = queryset.filter(location__city=city)
    if class_welcome == "yes":
        queryset = queryset.filter(class_welcome=True)
    elif class_welcome == "no":
        queryset = queryset.filter(class_welcome=False)
    return queryset


def attendance_rate_value(attendees, registered):
    """Calcule un taux de présence en % avec garde-fou division par zéro."""
    if not registered:
        return 0.0
    return round(attendees / registered * 100, 1)


def get_presence_by_group(workshops):
    """Taux de présence par lieu, commune et mois (agrégations ORM)."""
    by_location = list(
        workshops.values("location__name")
        .annotate(
            count=Count("id"),
            registered=Coalesce(Sum("number_registered"), 0),
            attendees=Coalesce(Sum("number_attendees"), 0),
        )
        .order_by("-count")
    )
    for row in by_location:
        row["attendance_rate"] = attendance_rate_value(
            row["attendees"], row["registered"]
        )

    by_commune = list(
        workshops.values("location__city")
        .annotate(
            count=Count("id"),
            registered=Coalesce(Sum("number_registered"), 0),
            attendees=Coalesce(Sum("number_attendees"), 0),
        )
        .order_by("-count")
    )
    for row in by_commune:
        row["attendance_rate"] = attendance_rate_value(
            row["attendees"], row["registered"]
        )

    return {"by_location": by_location, "by_commune": by_commune}


def get_distribution_stats(workshops):
    """Distribution des inscrits : médiane approximative + histogramme.

    La médiane est calculée en Python sur les valeurs triées (une seule
    requête values_list), l'histogramme par tranches en DB.
    """
    values = list(
        workshops.exclude(class_welcome=True)
        .exclude(number_registered__isnull=True)
        .order_by("number_registered")
        .values_list("number_registered", flat=True)
    )
    distribution = {
        "median": 0,
        "p25": 0,
        "p75": 0,
        "count": len(values),
        "histogram": [],
    }
    if values:
        n = len(values)
        distribution["median"] = float(values[n // 2])
        distribution["p25"] = float(values[n // 4])
        distribution["p75"] = float(values[(3 * n) // 4])
    for label, low, high in ATTENDANCE_TRANCHES:
        q = Q(number_registered__gte=low)
        if high is not None:
            q &= Q(number_registered__lte=high)
        count = workshops.exclude(class_welcome=True).filter(q).count()
        distribution["histogram"].append({"tranche": label, "count": count})
    return distribution


def get_poster_and_channel_stats(workshops, total):
    """Stats affiches + couverture des canaux de communication."""
    agg = workshops.aggregate(
        poster_required=Count("id", filter=Q(poster_required=True)),
        poster_valide=Count("id", filter=Q(poster_valide=True)),
        with_image=Count("id", filter=Q(image__isnull=False)),
        instagram=Count("id", filter=Q(instagram=True)),
        facebook=Count("id", filter=Q(facebook=True)),
        mail=Count("id", filter=Q(mail=True)),
        portail=Count("id", filter=Q(portail=True)),
        vdn=Count("id", filter=Q(vdn=True)),
        avg_registered=Coalesce(
            Avg("number_registered"), 0.0, output_field=models.FloatField()
        ),
    )
    channels = ["instagram", "facebook", "mail", "portail", "vdn"]
    coverage = {}
    for channel in channels:
        count = agg.get(channel, 0)
        coverage[channel] = {
            "count": count,
            "rate": round(count / total * 100, 1) if total else 0.0,
        }
    required = agg.get("poster_required", 0)
    poster = {
        "required": required,
        "valide": agg.get("poster_valide", 0),
        "with_image": agg.get("with_image", 0),
        "required_rate": round(required / total * 100, 1) if total else 0.0,
        "valide_rate": (
            round(agg.get("poster_valide", 0) / required * 100, 1)
            if required
            else 0.0
        ),
    }
    return {
        "poster": poster,
        "channels": coverage,
        "avg_registered": agg.get("avg_registered", 0),
    }


def get_top_flop_communes(commune_table_data, min_ateliers=MIN_ATELIERS_TOP_FLOP):
    """Top/flop communes et lieux avec seuil minimum d'ateliers."""
    eligible = [
        c
        for c in commune_table_data
        if c.get("total_ateliers", 0) >= min_ateliers
    ]
    by_rate = sorted(
        eligible, key=lambda c: c.get("attendance_rate", 0), reverse=True
    )
    by_volume = sorted(
        eligible, key=lambda c: c.get("total_participants", 0), reverse=True
    )
    return {
        "min_ateliers": min_ateliers,
        "top_presence": by_rate[:5],
        "flop_presence": list(reversed(by_rate[-5:])) if by_rate else [],
        "top_volume": by_volume[:5],
    }
