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


def get_stats_cache_key(year, location_id=None, city="", class_welcome="", month="", channel="", weekday="", slot=""):
    """Construit la clé de cache pour les stats ateliers."""
    key_city = city or "-"
    key_class = class_welcome or "-"
    key_month = month or "-"
    key_channel = channel or "-"
    key_weekday = weekday or "-"
    key_slot = slot or "-"
    # v3 : inclut mois + canal + jour semaine + créneau.
    return f"workshop_stats:{year}:{location_id or 0}:{key_city}:{key_class}:{key_month}:{key_channel}:{key_weekday}:{key_slot}:v3"


def apply_stats_filters(queryset, location_id=None, city="", class_welcome="", month="", channel="", weekday="", slot=""):
    """Applique les filtres lieu / ville / type / mois / canal / jour / créneau."""
    if location_id:
        queryset = queryset.filter(location_id=location_id)
    if city:
        queryset = queryset.filter(location__city=city)
    if class_welcome == "yes":
        queryset = queryset.filter(class_welcome=True)
    elif class_welcome == "no":
        queryset = queryset.filter(class_welcome=False)
    if month:
        try:
            queryset = queryset.filter(date__month=int(month))
        except (ValueError, TypeError):
            pass
    if channel in ("instagram", "facebook", "mail", "portail", "vdn"):
        queryset = queryset.filter(**{channel: True})
    if weekday:
        # Django week_day : 1=Dimanche, 2=Lundi, ..., 7=Samedi.
        try:
            queryset = queryset.filter(date__week_day=int(weekday))
        except (ValueError, TypeError):
            pass
    if slot in ("matin", "am", "soir"):
        # Créneau basé sur l'heure de début.
        if slot == "matin":
            queryset = queryset.filter(start_time__hour__lt=12)
        elif slot == "am":
            queryset = queryset.filter(start_time__hour__gte=12, start_time__hour__lt=17)
        else:
            queryset = queryset.filter(start_time__hour__gte=17)
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


CHANNEL_FIELDS = ("instagram", "facebook", "mail", "portail", "vdn")


def get_channel_cross_stats(workshops):
    """Croisement canal x performance en 1 seule requête.

    Pour chaque canal : ateliers relayés, inscrits cumulés, présents
    cumulés, taux de présence et moyenne d'inscrits.
    """
    annotations = {}
    for canal in CHANNEL_FIELDS:
        annotations[f"{canal}_count"] = Count("id", filter=Q(**{canal: True}))
        annotations[f"{canal}_registered"] = Coalesce(
            Sum("number_registered", filter=Q(**{canal: True})), 0
        )
        annotations[f"{canal}_attendees"] = Coalesce(
            Sum("number_attendees", filter=Q(**{canal: True})), 0
        )
    agg = workshops.aggregate(**annotations)
    rows = []
    for canal in CHANNEL_FIELDS:
        count = agg.get(f"{canal}_count", 0) or 0
        registered = agg.get(f"{canal}_registered", 0) or 0
        attendees = agg.get(f"{canal}_attendees", 0) or 0
        rows.append(
            {
                "channel": canal,
                "label": "VDN" if canal == "vdn" else canal.capitalize(),
                "count": count,
                "registered": registered,
                "attendees": attendees,
                "attendance_rate": attendance_rate_value(attendees, registered),
                "avg_registered": round(registered / count, 1) if count else 0.0,
            }
        )
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def get_month_type_cross(workshops):
    """Croisement mois x type (classiques vs accueils) en 1 requête."""
    from django.db.models.functions import ExtractMonth

    rows = (
        workshops.annotate(month=ExtractMonth("date"))
        .values("month")
        .annotate(
            classic_count=Count("id", filter=Q(class_welcome=False)),
            class_count=Count("id", filter=Q(class_welcome=True)),
            classic_registered=Coalesce(
                Sum("number_registered", filter=Q(class_welcome=False)), 0
            ),
            class_registered=Coalesce(
                Sum("number_registered", filter=Q(class_welcome=True)), 0
            ),
        )
        .order_by("month")
    )
    by_month = {r["month"]: r for r in rows if r["month"]}
    result = []
    for month in range(1, 13):
        data = by_month.get(month, {})
        result.append(
            {
                "month": month,
                "classic_count": data.get("classic_count", 0),
                "class_count": data.get("class_count", 0),
                "classic_registered": data.get("classic_registered", 0),
                "class_registered": data.get("class_registered", 0),
            }
        )
    return result


def get_commune_month_matrix(workshops, top_n=8):
    """Matrice communes (top N) x mois : nombre d'ateliers par case.

    2 requêtes max : top communes puis détail mois pour ces communes.
    """
    from django.db.models.functions import ExtractMonth

    top_cities = list(
        workshops.values("location__city")
        .annotate(total=Count("id"))
        .order_by("-total")[:top_n]
    )
    cities = [c["location__city"] or "Non défini" for c in top_cities]
    if not cities:
        return {"cities": [], "matrix": [], "months": list(range(1, 13))}
    real_cities = [c for c in cities if c != "Non défini"]
    has_undefined = "Non défini" in cities
    if has_undefined:
        base_qs = workshops.filter(
            Q(location__city__in=real_cities) | Q(location__city__isnull=True)
        ) if real_cities else workshops.filter(location__city__isnull=True)
    else:
        base_qs = workshops.filter(location__city__in=real_cities)
    detail = (
        base_qs.annotate(month=ExtractMonth("date"))
        .values("location__city", "month")
        .annotate(count=Count("id"))
        .order_by("location__city", "month")
    )
    grid = {(c or "Non défini", m): 0 for c in cities for m in range(1, 13)}
    for row in detail:
        key = (row["location__city"] or "Non défini", row["month"])
        if key in grid:
            grid[key] = row["count"]
    matrix = []
    for city in cities:
        months = [grid[(city, m)] for m in range(1, 13)]
        matrix.append({"commune": city, "months": months, "total": sum(months)})
    return {"cities": cities, "matrix": matrix, "months": list(range(1, 13))}


# ---------------------------------------------------------------------------
# A. Remplissage / performance (1 requête chacune, Python pour les ratios)
# ---------------------------------------------------------------------------

def get_fill_tranches(workshops):
    """Répartition des ateliers par taux de présence.

    Tranches : 0 inscrit, <50%, 50-80%, >80%, non renseigné.
    1 requête values_list, calcul Python (cohérent, pas de division SQL).
    """
    rows = list(
        workshops.values_list("number_registered", "number_attendees")
    )
    tranches = {"zero": 0, "low": 0, "mid": 0, "high": 0, "unknown": 0}
    for registered, attendees in rows:
        if registered is None or attendees is None:
            tranches["unknown"] += 1
        elif not registered:
            tranches["zero"] += 1
        else:
            rate = attendees / registered * 100
            if rate < 50:
                tranches["low"] += 1
            elif rate <= 80:
                tranches["mid"] += 1
            else:
                tranches["high"] += 1
    total = len(rows)
    return {"tranches": tranches, "total": total}


def get_noshow_top(workshops, limit=10):
    """Top des plus forts taux de no-show (inscrits > 0). 1 requête."""
    from django.db.models import ExpressionWrapper, FloatField

    return list(
        workshops.exclude(number_registered__isnull=True)
        .exclude(number_registered=0)
        .annotate(
            noshow_rate=ExpressionWrapper(
                100.0
                * (
                    models.F("number_registered")
                    - Coalesce("number_attendees", 0)
                )
                / models.F("number_registered"),
                output_field=FloatField(),
            )
        )
        .order_by("-noshow_rate")
        .values(
            "id", "name", "date", "location__city", "number_registered",
            "number_attendees", "noshow_rate",
        )[:limit]
    )


def get_zero_registered(workshops, limit=20):
    """Ateliers à 0 inscrit (ou non renseigné). 1 requête."""
    qs = workshops.filter(
        Q(number_registered=0) | Q(number_registered__isnull=True)
    ).select_related("location").order_by("date")
    total = qs.count()
    sample = list(
        qs.values("id", "name", "date", "location__city")[:limit]
    )
    return {"total": total, "sample": sample}


def get_pareto(workshops):
    """Part des inscrits apportée par le top 20% des ateliers. 1 requête."""
    values = sorted(
        [
            v or 0
            for v in workshops.exclude(number_registered__isnull=True).values_list(
                "number_registered", flat=True
            )
        ],
        reverse=True,
    )
    if not values:
        return {"top_count": 0, "total_count": 0, "top_share": 0.0, "total_registered": 0}
    import math

    top_n = max(1, math.ceil(len(values) * 0.2))
    total = sum(values)
    top_sum = sum(values[:top_n])
    return {
        "top_count": top_n,
        "total_count": len(values),
        "top_share": round(top_sum / total * 100, 1) if total else 0.0,
        "total_registered": total,
    }


def get_recurrence_by_name(workshops, limit=15):
    """Récurrence par intitulé : occurrences + moyenne. 1 requête."""
    return list(
        workshops.values("name")
        .annotate(
            count=Count("id"),
            avg_registered=Coalesce(
                Avg("number_registered"), 0.0,
                output_field=models.FloatField(),
            ),
            total_registered=Coalesce(Sum("number_registered"), 0),
        )
        .order_by("-count", "-total_registered")[:limit]
    )


# ---------------------------------------------------------------------------
# B. Temporalité : jour semaine / créneau / durée (1 requête chacune)
# ---------------------------------------------------------------------------

# Django week_day : 1=Dimanche, 2=Lundi, ..., 7=Samedi.
WEEKDAY_LABELS = {
    1: "Dimanche", 2: "Lundi", 3: "Mardi", 4: "Mercredi",
    5: "Jeudi", 6: "Vendredi", 7: "Samedi",
}
WEEKDAY_ORDER = [2, 3, 4, 5, 6, 7, 1]


def get_weekday_stats(workshops):
    """Ateliers / inscrits / présence par jour de semaine. 1 requête."""
    from django.db.models.functions import ExtractWeekDay

    rows = (
        workshops.annotate(weekday=ExtractWeekDay("date"))
        .values("weekday")
        .annotate(
            count=Count("id"),
            registered=Coalesce(Sum("number_registered"), 0),
            attendees=Coalesce(Sum("number_attendees"), 0),
        )
    )
    by_day = {r["weekday"]: r for r in rows if r["weekday"]}
    result = []
    for wd in WEEKDAY_ORDER:
        data = by_day.get(wd, {})
        registered = data.get("registered", 0) or 0
        attendees = data.get("attendees", 0) or 0
        result.append(
            {
                "weekday": wd,
                "label": WEEKDAY_LABELS[wd],
                "count": data.get("count", 0),
                "registered": registered,
                "attendees": attendees,
                "attendance_rate": attendance_rate_value(attendees, registered),
            }
        )
    return result


SLOT_LABELS = {"matin": "Matin (<12h)", "am": "Après-midi (12-17h)", "soir": "Soir (≥17h)"}


def get_slot_stats(workshops):
    """Ateliers / inscrits / présence par créneau horaire. 1 requête."""
    rows = (
        workshops.annotate(
            slot=models.Case(
                models.When(start_time__hour__lt=12, then=models.Value("matin")),
                models.When(start_time__hour__lt=17, then=models.Value("am")),
                default=models.Value("soir"),
                output_field=models.CharField(),
            )
        )
        .values("slot")
        .annotate(
            count=Count("id"),
            registered=Coalesce(Sum("number_registered"), 0),
            attendees=Coalesce(Sum("number_attendees"), 0),
        )
    )
    by_slot = {r["slot"]: r for r in rows}
    result = []
    for key in ("matin", "am", "soir"):
        data = by_slot.get(key, {})
        registered = data.get("registered", 0) or 0
        attendees = data.get("attendees", 0) or 0
        result.append(
            {
                "slot": key,
                "label": SLOT_LABELS[key],
                "count": data.get("count", 0),
                "registered": registered,
                "attendees": attendees,
                "attendance_rate": attendance_rate_value(attendees, registered),
            }
        )
    return result


def get_duration_stats(workshops):
    """Durée moyenne / médiane des ateliers (minutes). 1 requête."""
    pairs = list(
        workshops.exclude(start_time__isnull=True)
        .exclude(end_time__isnull=True)
        .values_list("start_time", "end_time")
    )
    minutes = []
    for start, end in pairs:
        try:
            delta = (
                end.hour * 60 + end.minute
            ) - (
                start.hour * 60 + start.minute
            )
            if delta > 0:
                minutes.append(delta)
        except AttributeError:
            continue
    if not minutes:
        return {"count": 0, "avg": 0.0, "median": 0.0}
    minutes.sort()
    n = len(minutes)
    return {
        "count": n,
        "avg": round(sum(minutes) / n, 1),
        "median": float(minutes[n // 2]),
    }


# ---------------------------------------------------------------------------
# C. Territoire / équité
# ---------------------------------------------------------------------------

def get_coverage_gaps(workshops, commune_table_data):
    """Communes avec lieu mais 0 atelier sur la période + équité des inscrits."""
    from .models import Location

    all_cities = sorted(
        {
            c
            for c in Location.objects.values_list("city", flat=True).distinct()
            if c
        }
    )
    active = {c.get("commune") for c in commune_table_data}
    gaps = [c for c in all_cities if c not in active]
    total_registered = sum(c.get("total_participants", 0) for c in commune_table_data)
    shares = []
    for c in sorted(commune_table_data, key=lambda x: x.get("total_participants", 0), reverse=True)[:8]:
        part = c.get("total_participants", 0)
        shares.append(
            {
                "commune": c.get("commune"),
                "registered": part,
                "share": round(part / total_registered * 100, 1) if total_registered else 0.0,
            }
        )
    return {"gaps": gaps, "shares": shares, "total_registered": total_registered}


def get_location_load(workshops):
    """Charge par lieu : ateliers + durée cumulée (minutes). 1 requête."""
    rows = list(
        workshops.select_related("location").values(
            "location__name", "start_time", "end_time"
        )
    )
    load = {}
    for r in rows:
        name = r["location__name"] or "Inconnu"
        entry = load.setdefault(name, {"location": name, "count": 0, "minutes": 0})
        entry["count"] += 1
        try:
            delta = (
                r["end_time"].hour * 60 + r["end_time"].minute
            ) - (
                r["start_time"].hour * 60 + r["start_time"].minute
            )
            if delta > 0:
                entry["minutes"] += delta
        except AttributeError:
            continue
    result = sorted(load.values(), key=lambda x: x["count"], reverse=True)[:10]
    return result


def _plural(n, singular, plural=None):
    """Accord simple pour les synthèses."""
    if n == 1:
        return singular
    return plural or singular + "s"


def _variation_wording(variation):
    """Formulation naturelle d'une variation en % (ou None si stable)."""
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
        data (dict): clés attendues — year, total_workshops,
            total_classics, total_accueils, total_registered,
            total_attendees, attendance_rate, total_communes,
            previous (dict|None avec year, workshops_variation,
            registered_variation), top_communes (list), months
            (list {label, count}), weekdays (list {label, count}),
            slots (list {label, count}), channels (list {label, count}),
            gaps (list), low_count (int), progress (list de
            (commune, variation)), decline (list), perimetre (str|None).

    Returns:
        dict: {"perimetre": str|None, "phrases": list[str]} — phrases
        déterministes, sans le périmètre (rendu à part dans le template).
    """
    year = data.get("year", "")
    total = data.get("total_workshops", 0) or 0
    phrases = []

    perimetre = data.get("perimetre")

    communes = data.get("total_communes", 0) or 0
    inscrits = data.get("total_registered", 0) or 0
    phrases.append(
        f"En {year}, {total} {_plural(total, 'atelier')} "
        f"ont été organisés dans {communes} {_plural(communes, 'commune')}, "
        f"réunissant {inscrits} {_plural(inscrits, 'inscrit')}."
    )

    classiques = data.get("total_classics", 0) or 0
    accueils = data.get("total_accueils", 0) or 0
    phrases.append(
        f"L'offre compte {classiques} {_plural(classiques, 'atelier classique', 'ateliers classiques')} "
        f"et {accueils} {_plural(accueils, 'accueil de classe', 'accueils de classe')}."
    )

    presents = data.get("total_attendees", 0) or 0
    taux = data.get("attendance_rate", 0) or 0
    phrases.append(
        f"Le taux de présence s'élève à {taux:.1f} %, "
        f"avec {presents} {_plural(presents, 'présent')}."
    )

    previous = data.get("previous")
    if previous:
        w_word = _variation_wording(previous.get("workshops_variation"))
        r_word = _variation_wording(previous.get("registered_variation"))
        phrases.append(
            f"Par rapport à {previous.get('year')} sur la même période, "
            f"les ateliers sont {w_word} et les inscrits {r_word}."
        )

    top = [c for c in (data.get("top_communes") or [])[:3] if c.get("commune")]
    if top:
        details = ", ".join(
            f"{c['commune']} ({c.get('total_ateliers', 0)} "
            f"{_plural(c.get('total_ateliers', 0), 'atelier')})"
            for c in top
        )
        phrases.append(f"L'activité se concentre sur {details}.")

    months = [m for m in (data.get("months") or []) if m.get("count", 0) > 0]
    if months:
        peak = max(months, key=lambda m: m["count"])
        phrases.append(
            f"Le mois le plus actif est {peak['label']} "
            f"avec {peak['count']} {_plural(peak['count'], 'atelier')}."
        )

    weekdays = [d for d in (data.get("weekdays") or []) if d.get("count", 0) > 0]
    slots = [s for s in (data.get("slots") or []) if s.get("count", 0) > 0]
    if weekdays and slots:
        best_day = max(weekdays, key=lambda d: d["count"])
        best_slot = max(slots, key=lambda s: s["count"])
        phrases.append(
            f"Le {best_day['label']} et le créneau {best_slot['label'].lower()} "
            f"sont les plus porteurs."
        )
    elif weekdays:
        best_day = max(weekdays, key=lambda d: d["count"])
        phrases.append(f"Le {best_day['label']} est le jour le plus porteur.")

    channels = [c for c in (data.get("channels") or []) if c.get("count", 0) > 0]
    if channels:
        top_channel = channels[0]
        phrases.append(
            f"Le canal dominant est {top_channel['label']} "
            f"({top_channel['count']} {_plural(top_channel['count'], 'atelier')} relayé{_plural(top_channel['count'], '', 's')})."
        )

    gaps = data.get("gaps") or []
    if gaps:
        shown = ", ".join(gaps[:4])
        extra = f" et {len(gaps) - 4} autres" if len(gaps) > 4 else ""
        phrases.append(
            f"{len(gaps)} {_plural(len(gaps), 'commune équipée', 'communes équipées')} "
            f"reste{_plural(len(gaps), '', 'nt')} sans atelier sur la période : {shown}{extra}."
        )
    else:
        phrases.append(
            "Toutes les communes équipées ont accueilli au moins un atelier."
        )

    progress = (data.get("progress") or [])[:2]
    decline = (data.get("decline") or [])[:2]
    if progress or decline:
        parts = []
        if progress:
            parts.append(
                "en progression : "
                + ", ".join(f"{c} (+{v})" for c, v in progress)
            )
        if decline:
            parts.append(
                "en retrait : "
                + ", ".join(f"{c} ({v})" for c, v in decline)
            )
        phrases.append("Par commune, " + " ; ".join(parts) + ".")

    low = data.get("low_count", 0) or 0
    if low > 0:
        phrases.append(
            f"Avec {low} {_plural(low, 'atelier')} sous les 50 % de présence, "
            f"une relance ciblée (rappels, horaires) reste le levier principal."
        )
    else:
        phrases.append(
            "Le niveau de présence est sain ; l'enjeu est de maintenir "
            "la régularité de l'offre."
        )

    return {"perimetre": perimetre, "phrases": phrases}
