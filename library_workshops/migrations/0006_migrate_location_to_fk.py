from django.db import migrations, models
import django.db.models.deletion


def set_old_locations_to_zero(apps, schema_editor):
    Workshop = apps.get_model('library_workshops', 'Workshop')
    Workshop.objects.all().update(location='0')


def fix_null_locations(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE library_workshops_workshop SET location_id = NULL WHERE location_id = 0;"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('visitor_tracking', '0001_initial'),
        ('library_workshops', '0005_alter_workshop_end_date_alter_workshop_location_and_more'),
    ]

    operations = [
        migrations.RunPython(
            set_old_locations_to_zero,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.RunSQL(
            "PRAGMA foreign_keys = OFF;",
            reverse_sql="PRAGMA foreign_keys = ON;"
        ),
        migrations.AlterField(
            model_name='workshop',
            name='location',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='workshops',
                to='visitor_tracking.location',
                verbose_name='Lieu'
            ),
        ),
        migrations.RunPython(
            fix_null_locations,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.RunSQL(
            "PRAGMA foreign_keys = ON;",
            reverse_sql="PRAGMA foreign_keys = OFF;"
        ),
    ]
