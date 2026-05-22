from django.db import migrations


def assign_locations_to_anor(apps, schema_editor):
    Location = apps.get_model('visitor_tracking', 'Location')
    User = apps.get_model('auth', 'User')
    try:
        anor = User.objects.get(username='anor')
        Location.objects.filter(user__isnull=True).update(user=anor)
    except User.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('visitor_tracking', '0002_location_user_alter_location_name'),
    ]

    operations = [
        migrations.RunPython(assign_locations_to_anor),
    ]
