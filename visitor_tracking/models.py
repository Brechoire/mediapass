from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Location(models.Model):
    """Espace de la médiathèque (Médiathèque, Ludothèque, etc.)"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='locations',
        verbose_name="Utilisateur",
        null=True,
        blank=True
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nom de l'espace",
        db_index=True
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description"
    )
    icon = models.CharField(
        max_length=50,
        default='bx-building',
        verbose_name="Icône",
        help_text="Classe CSS de l'icône BoxIcons (ex: bx-book, bx-building)"
    )
    color = models.CharField(
        max_length=7,
        default='#4F46E5',
        verbose_name="Couleur",
        help_text="Code couleur hexadécimal (ex: #4F46E5)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        db_index=True
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage",
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Espace"
        verbose_name_plural = "Espaces"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class VisitorCount(models.Model):
    """Comptage des visiteurs par jour et par espace"""
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='visitor_counts',
        verbose_name="Espace"
    )
    date = models.DateField(
        verbose_name="Date",
        db_index=True
    )
    count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Nombre de visiteurs"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_visitor_counts',
        verbose_name="Créé par"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_visitor_counts',
        verbose_name="Modifié par"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification"
    )

    class Meta:
        verbose_name = "Comptage visiteurs"
        verbose_name_plural = "Comptages visiteurs"
        unique_together = ('location', 'date')
        ordering = ['-date', 'location__order']

    def __str__(self):
        return f"{self.location.name} - {self.date}: {self.count} visiteurs"

