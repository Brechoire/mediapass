"""Crée le groupe « distribution » (comptes terrain, accès restreint).

Aucune permission Django n'est attachée : le contrôle se fait par nom
de groupe (voir distribution.views.is_distribution_agent), comme pour
le groupe « mediatheque ».
"""

from django.db import migrations


def create_distribution_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='distribution')


def remove_distribution_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='distribution').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('distribution', '0006_campagnelieuexclusion'),
    ]

    operations = [
        migrations.RunPython(
            create_distribution_group,
            remove_distribution_group,
        ),
    ]
