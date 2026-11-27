"""Normalisation et résolution des noms d'ateliers.

La liste des noms reste volontairement simple : seules la casse, les
accents, les espaces et la ponctuation sont neutralisés. Les variantes
de pluriel ou de format restent des noms distincts.
"""

from collections import defaultdict
import re
import unicodedata

from django.core.exceptions import ValidationError


def _strip_accents(value):
    """Supprime les accents et normalise les ligatures."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.replace("œ", "oe").replace("æ", "ae")


def normalize_workshop_name(value):
    """Construit la clé de comparaison d'un nom d'atelier."""
    text = _strip_accents(value).casefold()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_display_name(value):
    """Nettoie le libellé affiché sans changer sa casse ni sa ponctuation."""
    return " ".join(str(value or "").split())


def choose_canonical_name(variants):
    """Choisit le libellé canonique d'un groupe.

    Args:
        variants: itérable de tuples ``(nom, nombre_d_occurrences)``.

    Returns:
        str: Le nom le plus fréquent, puis le plus court, puis alphabétique.
    """
    return min(
        variants,
        key=lambda item: (
            -item[1],
            len(item[0]),
            item[0].casefold(),
            item[0],
        ),
    )[0]


def build_catalog_plan(name_counts):
    """Prépare les entrées canoniques à partir de noms et de leurs comptes.

    Args:
        name_counts: dict ``{nom: nombre_d_occurrences}``.

    Returns:
        list[tuple[str, str]]: couples ``(libellé_canonique, clé_normalisée)``.
    """
    groups = defaultdict(dict)
    for raw_name, count in name_counts.items():
        display = clean_display_name(raw_name)
        key = normalize_workshop_name(display)
        if not key:
            continue
        groups[key][display] = groups[key].get(display, 0) + int(count or 0)

    plan = []
    for key, display_counts in groups.items():
        canonical = choose_canonical_name(display_counts.items())
        plan.append((canonical, key))
    plan.sort(key=lambda item: (item[0].casefold(), item[0]))
    return plan


def resolve_workshop_name(raw_name):
    """Retourne l'entrée de liste correspondant au nom, ou la crée.

    Args:
        raw_name: Nom saisi par l'utilisateur.

    Returns:
        WorkshopName: L'entrée canonique existante ou nouvellement créée.

    Raises:
        ValidationError: Si le nom est vide ou uniquement composé de
            ponctuation, ou s'il dépasse les limites du modèle.
    """
    # Import différé pour éviter un cycle models -> naming -> models.
    from .models import WorkshopName

    display = clean_display_name(raw_name)
    key = normalize_workshop_name(display)
    if not key:
        raise ValidationError(
            "Le nom de l'atelier doit contenir au moins une lettre ou un chiffre."
        )
    if len(display) > 255:
        raise ValidationError(
            "Le nom de l'atelier ne peut pas dépasser 255 caractères."
        )
    if len(key) > 512:
        raise ValidationError("Le nom de l'atelier est trop long après normalisation.")

    entry, _created = WorkshopName.objects.get_or_create(
        normalized=key,
        defaults={"name": display},
    )
    return entry
