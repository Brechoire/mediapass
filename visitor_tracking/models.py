from django.core.exceptions import ValidationError
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


class Closure(models.Model):
    """Fermeture de la médiathèque (jour férié, congés, travaux...)."""

    KIND_CHOICES = [
        ("public_holiday", "Jour férié"),
        ("annual", "Fermeture annuelle"),
        ("works", "Travaux"),
        ("exceptional", "Fermeture exceptionnelle"),
        ("other", "Autre"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="visitor_closures",
        verbose_name="Médiathèque",
    )
    start_date = models.DateField("Début", db_index=True)
    end_date = models.DateField("Fin", db_index=True)
    kind = models.CharField(
        "Motif",
        max_length=20,
        choices=KIND_CHOICES,
        default="exceptional",
        db_index=True,
    )
    label = models.CharField("Précision", max_length=200, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_visitor_closures",
        verbose_name="Créé par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fermeture"
        verbose_name_plural = "Fermetures"
        ordering = ["-start_date", "-end_date"]
        indexes = [
            models.Index(
                fields=["user", "start_date", "end_date"],
                name="idx_closure_user_dates",
            )
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="closure_end_gte_start",
            )
        ]

    def clean(self):
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError(
                "La date de fin doit être postérieure ou égale à la date "
                "de début."
            )

    def __str__(self):
        return (
            f"{self.user.username} — {self.start_date:%d/%m/%Y} au "
            f"{self.end_date:%d/%m/%Y} ({self.get_kind_display()})"
        )

    @property
    def day_count(self):
        return (self.end_date - self.start_date).days + 1

