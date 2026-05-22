# Generated migration for visitor_tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name="Nom de l'espace")),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('icon', models.CharField(default='bx-building', help_text="Classe CSS de l'icône BoxIcons (ex: bx-book, bx-building)", max_length=50, verbose_name='Icône')),
                ('color', models.CharField(default='#4F46E5', help_text='Code couleur hexadécimal (ex: #4F46E5)', max_length=7, verbose_name='Couleur')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('order', models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Date de création')),
            ],
            options={
                'verbose_name': 'Espace',
                'verbose_name_plural': 'Espaces',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='VisitorCount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('count', models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Nombre de visiteurs')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Date de création')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Date de modification')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_visitor_counts', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visitor_counts', to='visitor_tracking.location', verbose_name='Espace')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_visitor_counts', to=settings.AUTH_USER_MODEL, verbose_name='Modifié par')),
            ],
            options={
                'verbose_name': 'Comptage visiteurs',
                'verbose_name_plural': 'Comptages visiteurs',
                'ordering': ['-date', 'location__order'],
                'unique_together': {('location', 'date')},
            },
        ),
    ]

