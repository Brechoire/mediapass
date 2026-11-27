"""Agrégations et regroupements pour le rapport complet des ateliers.

Le regroupement des intitulés reste volontairement prévisible : il ne
s'appuie pas sur une similarité floue, mais sur la normalisation des
variantes de format (casse, accents, pluriels, mots de format, support).
"""

from collections import Counter, defaultdict
import re
import unicodedata

from .services import attendance_rate_value

# Mots vides français : ils ne portent pas le sujet de l'animation.
STOP_WORDS = {
    "a",
    "au",
    "aux",
    "avec",
    "c",
    "ce",
    "ces",
    "cet",
    "cette",
    "chez",
    "d",
    "de",
    "des",
    "dans",
    "du",
    "en",
    "et",
    "j",
    "l",
    "la",
    "le",
    "les",
    "m",
    "ma",
    "mes",
    "mon",
    "n",
    "nos",
    "notre",
    "of",
    "par",
    "pour",
    "qu",
    "s",
    "sa",
    "ses",
    "son",
    "sous",
    "sur",
    "t",
    "ta",
    "tes",
    "the",
    "ton",
    "un",
    "une",
    "vos",
    "votre",
    "and",
}

# Mots qui décrivent le format de l'atelier, pas son sujet.
FORMAT_TOKENS = {
    "animation",
    "animations",
    "apprend",
    "apprendre",
    "apprends",
    "atelier",
    "ateliers",
    "autour",
    "cafe",
    "cafes",
    "comme",
    "connaissance",
    "construire",
    "construis",
    "construisez",
    "creation",
    "creations",
    "cree",
    "creer",
    "creons",
    "creez",
    "debat",
    "debats",
    "decouverte",
    "decouvertes",
    "decouvre",
    "decouvrez",
    "decouvrir",
    "fabrique",
    "fabriquer",
    "initiation",
    "initie",
    "initier",
    "pratique",
    "pratiques",
    "pro",
    "professionnel",
    "professionnelle",
    "programme",
    "programmer",
    "propre",
    "propres",
    "realise",
    "realiser",
    "rencontre",
    "rencontres",
    "seance",
    "seances",
    "soiree",
    "soirees",
    "special",
    "speciale",
    "speciaux",
    "stage",
    "stages",
    "theme",
    "themes",
    "tournoi",
    "tournois",
    "veillee",
    "veillees",
}

# Mots de support ou de lieu : retirés uniquement s'il reste un sujet.
SUPPORT_TOKENS = {
    "alsh",
    "csc",
    "face",
    "fagne",
    "numerique",
    "numeriques",
    "tablette",
    "tablettes",
    "thierache",
}

# Quelques abbreviations métier observées dans les intitulés réels.
TITLE_KEY_ALIASES = {
    "construction robot": "robot",
    "simulateur conduite": "simulateur",
}

IRREGULAR_SINGULARS = {
    "cafes": "cafe",
    "jeux": "jeux",
    "paques": "paque",
    "photos": "photo",
    "videos": "video",
}

EMPTY_KEY = "sans intitule"
EMPTY_LABEL = "Sans intitulé"
UNDEFINED_COMMUNE = "Non défini"


def _strip_accents(value):
    """Supprime les accents et normalise les ligatures."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.replace("œ", "oe").replace("æ", "ae")


def _singularize(token):
    """Normalise les pluriels simples sans casser les mots en -is/-us."""
    token = IRREGULAR_SINGULARS.get(token, token)
    if len(token) > 4 and token.endswith("s"):
        if token.endswith(("is", "us", "ss")):
            return token
        return token[:-1]
    return token


def _prepare_parentheticals(value):
    """Retire les parenthèses de programme/partenaire, garde les thèmes."""
    text = (value or "").replace("’", "'").replace("‘", "'")

    def _drop_parenthesis(match):
        content = match.group(1).strip()
        lower = _strip_accents(content).lower()
        if (
            "," in content
            or "..." in content
            or lower.startswith(("csc", "face", "alsh", "intercentre", "inter centre"))
        ):
            return " "
        return f" {content} "

    return re.sub(r"\(([^)]*)\)", _drop_parenthesis, text)


def _remove_inter_centre(text):
    text = re.sub(r"\binter[\s-]*centres?\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\bintercentres?\b", " ", text, flags=re.IGNORECASE)


def _tokenize(value):
    """Retourne les tokens significatifs d'un intitulé."""
    text = _strip_accents(_prepare_parentheticals(value)).lower()
    text = _remove_inter_centre(text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [_singularize(token) for token in text.split()]
    return [token for token in tokens if len(token) > 1 and token not in STOP_WORDS]


def _clean_label(value):
    """Construit un libellé lisible en retirant les mots de format."""
    text = _prepare_parentheticals(value)
    text = _remove_inter_centre(text)
    tokens = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿŒœ]+", text)
    kept = []
    for token in tokens:
        normalized = _singularize(_strip_accents(token).lower())
        if (
            normalized in STOP_WORDS
            or normalized in FORMAT_TOKENS
            or normalized in SUPPORT_TOKENS
        ):
            continue
        kept.append(token)

    label = " ".join(kept).strip(" -–—:;,.")
    if not label:
        normalized_tokens = {
            _singularize(_strip_accents(token).lower()) for token in tokens
        }
        if "tablette" in normalized_tokens:
            return "Tablette"
        return ""
    label = label[0].upper() + label[1:]
    return label


def _format_weight(value):
    """Nombre de mots de format/support dans un intitulé."""
    tokens = _tokenize(value)
    return sum(
        1 for token in tokens if token in FORMAT_TOKENS or token in SUPPORT_TOKENS
    )


def canonical_animation_key(title):
    """Construit la clé de regroupement d'un intitulé d'animation.

    Les variantes de format comme « Découverte Canva » et « Initiation
    Canva » partagent la même clé. Les sujets différents restent séparés.
    """
    tokens = _tokenize(title)

    # « Intelligence artificielle » et « IA » désignent le même sujet.
    if "intelligence" in tokens and "artificielle" in tokens:
        return "ia"

    subject = [token for token in tokens if token not in FORMAT_TOKENS]
    core = [token for token in subject if token not in SUPPORT_TOKENS]

    if not core:
        if "tablette" in subject:
            return "tablette"
        if not subject:
            return EMPTY_KEY
        return " ".join(subject)

    key = " ".join(core)
    return TITLE_KEY_ALIASES.get(key, key)


def _select_label(names):
    """Choisit un libellé unique, le plus neutre possible."""
    if not names:
        return EMPTY_LABEL
    unique_names = set(names)
    if len(unique_names) == 1:
        return next(iter(unique_names))
    counts = Counter(names)
    best = None
    for name in unique_names:
        label = _clean_label(name) or name or EMPTY_LABEL
        candidate = (
            _format_weight(name),
            len(label),
            label.casefold(),
            -counts[name],
            len(name),
            name,
            label,
        )
        if best is None or candidate < best:
            best = candidate
    return best[-1] if best else EMPTY_LABEL


def _empty_aggregate():
    return {
        "sessions": 0,
        "registered": 0,
        "attendees": 0,
        "class_welcome": 0,
        "names": Counter(),
        "communes": set(),
        "first_date": None,
        "last_date": None,
    }


def _add_row(aggregate, row):
    """Ajoute un atelier à un agrégat de séances."""
    aggregate["sessions"] += 1
    aggregate["registered"] += int(row["number_registered"] or 0)
    aggregate["attendees"] += int(row["number_attendees"] or 0)
    if row["class_welcome"]:
        aggregate["class_welcome"] += 1
    aggregate["names"][row["name"]] += 1
    aggregate["communes"].add(row["location__city"] or UNDEFINED_COMMUNE)

    row_date = row["date"]
    if row_date:
        if aggregate["first_date"] is None or row_date < aggregate["first_date"]:
            aggregate["first_date"] = row_date
        if aggregate["last_date"] is None or row_date > aggregate["last_date"]:
            aggregate["last_date"] = row_date


def _finalize_aggregate(aggregate, key, label):
    return {
        "key": key,
        "label": label,
        "variants": sorted(aggregate["names"]),
        "sessions": aggregate["sessions"],
        "registered": aggregate["registered"],
        "attendees": aggregate["attendees"],
        "attendance_rate": attendance_rate_value(
            aggregate["attendees"], aggregate["registered"]
        ),
        "class_welcome": aggregate["class_welcome"],
        "first_date": aggregate["first_date"],
        "last_date": aggregate["last_date"],
    }


def build_animation_report(workshops):
    """Agrège les ateliers par animation et par commune.

    Args:
        workshops: QuerySet d'ateliers déjà filtré.

    Returns:
        dict: Groupes d'animations, détail par commune et totaux.
    """
    rows = list(
        workshops.values(
            "id",
            "name",
            "date",
            "class_welcome",
            "number_registered",
            "number_attendees",
            "location__city",
            "location__name",
        ).order_by("location__city", "date", "name")
    )

    global_groups = {}
    commune_groups = defaultdict(
        lambda: {
            "aggregate": _empty_aggregate(),
            "animations": {},
        }
    )

    for row in rows:
        key = canonical_animation_key(row["name"])
        city = row["location__city"] or UNDEFINED_COMMUNE

        global_group = global_groups.setdefault(key, _empty_aggregate())
        _add_row(global_group, row)

        commune_group = commune_groups[city]
        _add_row(commune_group["aggregate"], row)
        commune_animation = commune_group["animations"].setdefault(
            key, _empty_aggregate()
        )
        _add_row(commune_animation, row)

    labels = {
        key: _select_label(aggregate["names"])
        for key, aggregate in global_groups.items()
    }

    groups = []
    for key, aggregate in global_groups.items():
        group = _finalize_aggregate(aggregate, key, labels[key])
        group["communes"] = sorted(aggregate["communes"])
        group["commune_count"] = len(group["communes"])
        groups.append(group)

    groups.sort(
        key=lambda group: (
            -group["sessions"],
            -group["registered"],
            group["label"].casefold(),
        )
    )

    by_commune = []
    for city, commune_group in commune_groups.items():
        aggregate = commune_group["aggregate"]
        animations = []
        for key, animation_aggregate in commune_group["animations"].items():
            animation = _finalize_aggregate(
                animation_aggregate, key, labels.get(key, EMPTY_LABEL)
            )
            animations.append(animation)

        animations.sort(
            key=lambda animation: (
                -animation["sessions"],
                -animation["registered"],
                animation["label"].casefold(),
            )
        )

        by_commune.append(
            {
                "commune": city,
                "total_ateliers": aggregate["sessions"],
                "class_welcome": aggregate["class_welcome"],
                "classics": aggregate["sessions"] - aggregate["class_welcome"],
                "animations_count": len(animations),
                "registered": aggregate["registered"],
                "attendees": aggregate["attendees"],
                "attendance_rate": attendance_rate_value(
                    aggregate["attendees"], aggregate["registered"]
                ),
                "animations": animations,
                "first_date": aggregate["first_date"],
                "last_date": aggregate["last_date"],
            }
        )

    by_commune.sort(
        key=lambda commune: (
            -commune["total_ateliers"],
            commune["commune"].casefold(),
        )
    )

    total_registered = sum(int(row["number_registered"] or 0) for row in rows)
    total_attendees = sum(int(row["number_attendees"] or 0) for row in rows)
    total_class_welcome = sum(1 for row in rows if row["class_welcome"])
    class_welcome_registered = sum(
        int(row["number_registered"] or 0) for row in rows if row["class_welcome"]
    )
    class_welcome_attendees = sum(
        int(row["number_attendees"] or 0) for row in rows if row["class_welcome"]
    )
    classics_registered = total_registered - class_welcome_registered
    classics_attendees = total_attendees - class_welcome_attendees

    return {
        "groups": groups,
        "by_commune": by_commune,
        "merged_groups": [group for group in groups if len(group["variants"]) > 1],
        "totals": {
            "animations": len(groups),
            "sessions": len(rows),
            "registered": total_registered,
            "attendees": total_attendees,
            "attendance_rate": attendance_rate_value(total_attendees, total_registered),
            "class_welcome": total_class_welcome,
            "classics": len(rows) - total_class_welcome,
            "classics_registered": classics_registered,
            "classics_attendees": classics_attendees,
            "classics_attendance_rate": attendance_rate_value(
                classics_attendees, classics_registered
            ),
            "class_welcome_registered": class_welcome_registered,
            "class_welcome_attendees": class_welcome_attendees,
            "class_welcome_attendance_rate": attendance_rate_value(
                class_welcome_attendees, class_welcome_registered
            ),
            "communes": len(by_commune),
        },
        "has_data": bool(rows),
    }
