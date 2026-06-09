import uuid

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from visitor_tracking.models import Location as VisitorLocation

from app.validators import validate_image_extension


class Workshop(models.Model):
    """Modèle pour représenter un atelier de la médiathèque"""

    # Champs principaux
    title = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Titre de l'atelier",
        help_text="Ex: Atelier de Lecture pour Enfants",
    )

    description = models.TextField(
        verbose_name="Description", help_text="Description détaillée de l'atelier"
    )

    # Dates et horaires
    start_date = models.DateField(verbose_name="Date de début", db_index=True)

    end_date = models.DateField(
        verbose_name="Date de fin",
        null=True,
        blank=True,
        help_text="Laissez vide si l'atelier se déroule sur une seule journée",
        db_index=True,
    )

    start_time = models.TimeField(verbose_name="Heure de début")

    end_time = models.TimeField(verbose_name="Heure de fin")

    # Lieu et capacité
    location = models.ForeignKey(
        VisitorLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workshops",
        verbose_name="Lieu",
    )

    max_participants = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Nombre maximum de participants",
    )

    # Affiche et visuel
    poster = models.ImageField(
        upload_to="workshop_posters/",
        null=True,
        blank=True,
        verbose_name="Affiche de l'atelier",
        validators=[validate_image_extension],
    )

    # Tranche d'âge
    is_all_ages = models.BooleanField(
        default=True,
        verbose_name="Tout public",
        help_text="Cochez si l'atelier est ouvert à tous les âges",
    )

    min_age = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Âge minimum",
        help_text="Âge minimum requis (0-100 ans)",
    )

    max_age = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Âge maximum",
        help_text="Âge maximum autorisé (0-100 ans)",
    )

    # Newsletter et métadonnées
    newsletter = models.BooleanField(
        default=True,
        verbose_name="Newsletter",
        help_text="Cochez pour envoyer une newsletter pour cet atelier",
        db_index=True,
    )

    reminder_sent = models.BooleanField(
        default=False,
        verbose_name="Rappel envoyé",
        help_text="Indique si le rappel J-1 a été envoyé",
        db_index=True,
    )

    is_class_welcome = models.BooleanField(
        default=False,
        verbose_name="Accueil de classe",
        help_text="Cochez si cet atelier peut accueillir des classes",
        db_index=True,
    )

    # Informations de création
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_workshops",
        verbose_name="Créé par",
    )

    recurrence_group = models.ForeignKey(
        "RecurrencePattern",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Groupe de récurrence",
        related_name="workshops",
    )

    recurrence_modified = models.BooleanField(
        default=False,
        verbose_name="Occurrence modifiée",
        help_text="True si cette occurrence a été éditée individuellement",
    )

    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )

    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Atelier"
        verbose_name_plural = "Ateliers"
        ordering = ["start_date", "start_time"]
        indexes = [
            models.Index(
                fields=["start_date", "start_time"], name="idx_workshop_start"
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_single_day(self):
        """Vérifie si l'atelier se déroule sur une seule journée"""
        return self.end_date is None or self.start_date == self.end_date

    @property
    def current_participants_count(self):
        """Retourne le nombre actuel de participants inscrits (utilise l'annotation si disponible)"""
        if hasattr(self, "confirmed_count"):
            return self.confirmed_count
        return self.participants.filter(status="confirmed").count()

    @property
    def waiting_list_count(self):
        """Retourne le nombre de personnes en liste d'attente (utilise l'annotation si disponible)"""
        if hasattr(self, "waiting_count"):
            return self.waiting_count
        return self.participants.filter(status="waiting").count()

    @property
    def available_spots(self):
        """Retourne le nombre de places disponibles"""
        return max(0, self.max_participants - self.current_participants_count)

    @property
    def is_full(self):
        """Vérifie si l'atelier est complet"""
        return self.current_participants_count >= self.max_participants

    @property
    def overbooking_count(self):
        """Retourne le nombre de participants en surcapacité (positif si surcapacité, 0 sinon)"""
        return max(0, self.current_participants_count - self.max_participants)

    @property
    def is_overbooked(self):
        """Vérifie si l'atelier dépasse sa capacité"""
        return self.current_participants_count > self.max_participants

    @property
    def is_past(self):
        """Vérifie si l'atelier est passé"""
        today = timezone.now().date()
        return self.start_date < today

    @property
    def is_upcoming(self):
        """Vérifie si l'atelier est à venir"""
        today = timezone.now().date()
        return self.start_date >= today

    @property
    def age_range_display(self):
        """Retourne l'affichage de la tranche d'âge"""
        if self.is_all_ages:
            return "Tout public"

        if self.min_age is not None and self.max_age is not None:
            if self.min_age == self.max_age:
                return f"{self.min_age} ans"
            else:
                return f"De {self.min_age} à {self.max_age} ans"
        elif self.min_age is not None:
            return f"À partir de {self.min_age} ans"
        elif self.max_age is not None:
            return f"Jusqu'à {self.max_age} ans"
        else:
            return "Tout public"

    @property
    def confirmed_participants(self):
        """Retourne les participants confirmés (utilise le cache prefetch si disponible)"""
        if hasattr(self, "_confirmed_prefetched") and hasattr(
            self, "confirmed_participants_list"
        ):
            return self.confirmed_participants_list
        return self.participants.filter(status="confirmed")

    @property
    def waiting_participants(self):
        """Retourne les participants en liste d'attente (utilise le cache prefetch si disponible)"""
        if hasattr(self, "_waiting_prefetched") and hasattr(
            self, "waiting_participants_list"
        ):
            return self.waiting_participants_list
        return self.participants.filter(status="waiting")

    def clean(self):
        """Validation personnalisée pour les tranches d'âge"""
        super().clean()

        if not self.is_all_ages:
            if self.min_age is None and self.max_age is None:
                raise ValidationError(
                    "Veuillez spécifier au moins un âge minimum ou maximum."
                )

            if (
                self.min_age is not None
                and self.max_age is not None
                and self.min_age > self.max_age
            ):
                raise ValidationError(
                    "L'âge minimum ne peut pas être supérieur à l'âge maximum."
                )


class WorkshopParticipant(models.Model):
    """Modèle pour représenter un participant à un atelier"""

    # Statuts de participation
    STATUS_CHOICES = [
        ("confirmed", "Confirmé"),
        ("waiting", "Liste d'attente"),
        ("cancelled", "Annulé"),
    ]

    # Relations
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Atelier",
    )

    # Informations du participant
    first_name = models.CharField(max_length=50, verbose_name="Prénom")

    last_name = models.CharField(max_length=50, verbose_name="Nom")

    age = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(120)],
        verbose_name="Âge",
        db_index=True,
    )

    # Informations de contact (optionnelles)
    email = models.EmailField(null=True, blank=True, verbose_name="Email")

    phone = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="Téléphone"
    )

    # Statut et métadonnées
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmed",
        verbose_name="Statut",
        db_index=True,
    )

    registration_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date d'inscription", db_index=True
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notes",
        help_text="Informations supplémentaires sur le participant",
    )

    # Informations de gestion
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_participants",
        verbose_name="Ajouté par",
    )

    # Gestion des réservations de groupe
    is_group_leader = models.BooleanField(
        default=False,
        verbose_name="Responsable du groupe",
        help_text="Cochez si cette personne est responsable d'un groupe",
        db_index=True,
    )

    group_leader = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="group_members",
        verbose_name="Responsable du groupe",
        help_text="Responsable du groupe si ce participant fait partie d'un groupe",
    )

    group_size = models.PositiveIntegerField(
        default=1,
        verbose_name="Taille du groupe",
        help_text="Nombre total de personnes dans le groupe (incluant le responsable)",
    )

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
        ordering = ["registration_date"]
        indexes = [
            models.Index(
                fields=["workshop", "status"], name="idx_participant_ws_status"
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.workshop.title}"

    @property
    def full_name(self):
        """Retourne le nom complet du participant"""
        return f"{self.first_name} {self.last_name}"

    @property
    def age_display(self):
        """Retourne l'âge avec le bon format d'affichage"""
        if self.age == 1:
            return "1 an"
        return f"{self.age} ans"

    @property
    def is_in_group(self):
        """Vérifie si le participant fait partie d'un groupe"""
        return self.group_leader is not None or self.is_group_leader

    @property
    def group_display(self):
        """Retourne l'affichage du groupe"""
        if self.is_group_leader:
            return f"Responsable (groupe de {self.group_size})"
        elif self.group_leader:
            return f"Membre du groupe de {self.group_leader.full_name}"
        else:
            return "Individuel"

    @property
    def group_members_count(self):
        """Retourne le nombre de membres dans le groupe"""
        if self.is_group_leader:
            return self.group_members.count()
        elif self.group_leader:
            return self.group_leader.group_members.count()
        else:
            return 1


class WorkshopCategory(models.Model):
    """Modèle pour catégoriser les ateliers"""

    name = models.CharField(
        max_length=100, unique=True, verbose_name="Nom de la catégorie"
    )

    description = models.TextField(null=True, blank=True, verbose_name="Description")

    color = models.CharField(
        max_length=7,
        default="#007bff",
        verbose_name="Couleur",
        help_text="Code couleur hexadécimal (ex: #007bff)",
    )

    icon = models.CharField(
        max_length=50,
        default="bx-book",
        verbose_name="Icône",
        help_text="Classe CSS de l'icône (ex: bx-book)",
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")

    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Catégorie d'atelier"
        verbose_name_plural = "Catégories d'ateliers"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RecurrencePattern(models.Model):
    """Paramètres de récurrence pour générer des séries d'ateliers"""

    FREQUENCY_CHOICES = [
        ("weekly", "Toutes les semaines"),
        ("biweekly", "Toutes les 2 semaines"),
        ("monthly", "Tous les mois"),
    ]

    group = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        db_index=True,
        verbose_name="Identifiant du groupe",
    )

    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Créé par"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )

    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, verbose_name="Fréquence"
    )

    interval = models.PositiveIntegerField(
        default=1,
        verbose_name="Intervalle",
        help_text="Toutes les X semaines (ignoré pour mensuel)",
    )

    days_of_week = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Jours de la semaine",
        help_text="Liste des index de jours (0=Lundi…5=Samedi)",
    )

    period_start = models.DateField(verbose_name="Date de début")

    period_end = models.DateField(verbose_name="Date de fin")

    excluded_dates = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Dates exclues",
        help_text="Liste des dates ISO à exclure",
    )

    month_day = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Jour du mois",
        help_text="Pour récurrence mensuelle : 15 = le 15 du mois",
    )

    # Copie des données de base pour regénération
    title = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(verbose_name="Description")
    start_time = models.TimeField(verbose_name="Heure de début")
    end_time = models.TimeField(verbose_name="Heure de fin")
    location = models.ForeignKey(
        VisitorLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Lieu",
    )
    max_participants = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Participants max",
    )
    is_all_ages = models.BooleanField(default=True, verbose_name="Tout public")
    min_age = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Âge minimum"
    )
    max_age = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Âge maximum"
    )
    newsletter = models.BooleanField(default=True, verbose_name="Newsletter")
    is_class_welcome = models.BooleanField(
        default=False, verbose_name="Accueil de classe"
    )

    class Meta:
        verbose_name = "Pattern de récurrence"
        verbose_name_plural = "Patterns de récurrence"

    def __str__(self):
        return f"{self.get_frequency_display()} — {self.title} ({self.period_start}→{self.period_end})"


class SchoolHoliday(models.Model):
    """Périodes de vacances scolaires pour exclusion automatique"""

    name = models.CharField(max_length=200, verbose_name="Nom")
    start_date = models.DateField(verbose_name="Date de début", db_index=True)
    end_date = models.DateField(verbose_name="Date de fin")
    zone = models.CharField(
        max_length=1,
        choices=[("A", "Zone A"), ("B", "Zone B"), ("C", "Zone C")],
        default="B",
        verbose_name="Zone",
        db_index=True,
    )

    class Meta:
        verbose_name = "Vacance scolaire"
        verbose_name_plural = "Vacances scolaires"
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.name} ({self.start_date}→{self.end_date})"
