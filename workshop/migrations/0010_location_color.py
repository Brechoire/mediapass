"""Couleur des lieux pour la vue trimestrielle."""

import django.core.validators
from django.db import migrations, models


# Palette déterministe : Anor / « Le 36 » en rose, les autres distincts.
LOCATION_COLORS = {
    "anor": "#ec4899",
    "le 36": "#ec4899",
    "fourmies": "#4a6fa5",
    "médiathèque de fourmies": "#4a6fa5",
    "gymnase marie-josé pérec": "#2563eb",
    "écomusée": "#0891b2",
    "glageon": "#059669",
    "bibliothèque de glageon": "#059669",
    "momignies": "#7c3aed",
    "bibliothèque de momignies": "#7c3aed",
    "eppe-sauvage": "#d97706",
    "médiathèque eppe-sauvage": "#d97706",
    "école eppe-sauvage": "#b45309",
    "trélon": "#dc2626",
    "médiathèque de trélon": "#dc2626",
    "féron": "#ea580c",
    "médiathèque de féron": "#ea580c",
    "école de féron": "#c2410c",
    "wignehies": "#65a30d",
    "médiathèque de wignehies": "#65a30d",
    "alsh wignehies": "#4d7c0f",
    "wallers-en-fagne": "#0d9488",
    "ohain": "#a855f7",
    "école d'ohain": "#a855f7",
}

FALLBACK_PALETTE = [
    "#4a6fa5",
    "#059669",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#dc2626",
    "#65a30d",
    "#ea580c",
    "#0d9488",
    "#a855f7",
    "#e11d48",
    "#2563eb",
    "#ca8a04",
    "#4d7c0f",
    "#b45309",
]


def _color_for(name, city, index):
    for key in (name or "", city or ""):
        normalized = key.strip().lower()
        if normalized in LOCATION_COLORS:
            return LOCATION_COLORS[normalized]
    return FALLBACK_PALETTE[index % len(FALLBACK_PALETTE)]


def assign_location_colors(apps, schema_editor):
    Location = apps.get_model("workshop", "Location")
    for index, location in enumerate(
        Location.objects.order_by("name", "city", "pk")
    ):
        color = _color_for(location.name, location.city, index)
        Location.objects.filter(pk=location.pk).update(color=color)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("workshop", "0009_workshop_audit_series"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="color",
            field=models.CharField(
                default="#4a6fa5",
                help_text=(
                    "Couleur utilisée dans la vue trimestrielle "
                    "(ex. #ec4899 pour le rose)."
                ),
                max_length=7,
                validators=[
                    django.core.validators.RegexValidator(
                        message="La couleur doit être au format hexadécimal (ex. #ec4899).",
                        regex="^#[0-9A-Fa-f]{6}$",
                    )
                ],
                verbose_name="Couleur",
            ),
        ),
        migrations.RunPython(assign_location_colors, noop),
    ]
