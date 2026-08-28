from django.db import migrations


def seed_presets(apps, schema_editor):
    HeaderPreset = apps.get_model("newsletter", "HeaderPreset")
    defaults = [
        {
            "name": "Standard gauche",
            "header_height": "default",
            "header_align": "left",
            "title_color": "",
            "text_color": "",
            "overlay_strength": "0.35",
        },
        {
            "name": "Grand centré",
            "header_height": "large",
            "header_align": "center",
            "title_color": "",
            "text_color": "",
            "overlay_strength": "0.45",
        },
        {
            "name": "Compact gauche",
            "header_height": "compact",
            "header_align": "left",
            "title_color": "",
            "text_color": "",
            "overlay_strength": "0.35",
        },
    ]
    for data in defaults:
        HeaderPreset.objects.get_or_create(name=data["name"], defaults=data)


def unseed_presets(apps, schema_editor):
    HeaderPreset = apps.get_model("newsletter", "HeaderPreset")
    HeaderPreset.objects.filter(name__in=["Standard gauche", "Grand centré", "Compact gauche"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("newsletter", "0012_add_section_header_overlay"),
    ]

    operations = [
        migrations.RunPython(seed_presets, unseed_presets),
    ]
