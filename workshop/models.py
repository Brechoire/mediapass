"""Modèles de données pour la gestion des ateliers."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from app.validators import (
    validate_image_content,
    validate_image_extension,
    validate_image_size,
    workshop_image_upload_to,
)
from .naming import normalize_workshop_name


class Location(models.Model):
    """Modèle représentant un lieu où se déroulent les ateliers.

    Attributes:
        name (str): Nom du lieu.
        address (str): Adresse du lieu.
        zip_code (str): Code postal du lieu.
        city (str): Ville du lieu.
    """

    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    zip_code = models.CharField(max_length=5)
    city = models.CharField(max_length=255, db_index=True)

    class Meta:
        verbose_name = "Lieu"
        verbose_name_plural = "Lieux"
        ordering = ["name"]

    def __str__(self):
        """Retourne une représentation textuelle du lieu.

        Returns:
            str: Le nom du lieu.
        """
        return self.name


class WorkshopName(models.Model):
    """Nom canonique d'atelier proposé dans les formulaires.

    La liste est indépendante des ateliers : un nom peut être préparé à
    l'avance, et reste disponible même si aucun atelier ne l'utilise.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Nom de l'atelier",
        help_text=(
            "Nom proposé dans les formulaires d'atelier. La casse, les "
            "accents et la ponctuation sont normalisés pour éviter les "
            "doublons."
        ),
    )
    normalized = models.CharField(
        max_length=512,
        unique=True,
        editable=False,
        verbose_name="Clé normalisée",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Nom d'atelier"
        verbose_name_plural = "Noms d'atelier"

    def __str__(self):
        """Retourne le libellé canonique."""
        return self.name

    def clean(self):
        """Valide et normalise le nom avant l'enregistrement."""
        super().clean()
        self.name = " ".join((self.name or "").split())
        self.normalized = normalize_workshop_name(self.name)
        if not self.normalized:
            raise ValidationError(
                {
                    "name": (
                        "Le nom doit contenir au moins une lettre ou un "
                        "chiffre."
                    )
                }
            )
        duplicate = (
            WorkshopName.objects.exclude(pk=self.pk)
            .filter(normalized=self.normalized)
            .first()
        )
        if duplicate:
            raise ValidationError(
                {
                    "name": (
                        f"Ce nom existe déjà sous la forme « {duplicate.name} »."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Calcule la clé normalisée avant la sauvegarde."""
        self.name = " ".join((self.name or "").split())
        self.normalized = normalize_workshop_name(self.name)
        if not self.normalized:
            raise ValidationError(
                {
                    "name": (
                        "Le nom doit contenir au moins une lettre ou un "
                        "chiffre."
                    )
                }
            )
        super().save(*args, **kwargs)


class Workshop(models.Model):
    """Modèle représentant un atelier.

    Attributes:
        location (Location): Lieu où se déroule l'atelier.
        name (str): Nom de l'atelier.
        date (date): Date de début de l'atelier.
        date_end (date): Date de fin de l'atelier (optionnel).
        start_time (time): Heure de début.
        end_time (time): Heure de fin.
        poster_required (bool): Indique si une affiche est requise.
        image (ImageField): Affiche de l'atelier (optionnel).
        number_registered (int): Nombre de personnes inscrites.
        number_attendees (int): Nombre de participants effectifs.
        class_welcome (bool): Indique si c'est un accueil de classe.
        instagram (bool): Publication sur Instagram.
        facebook (bool): Publication sur Facebook.
        mail (bool): Envoi par email.
        portail (bool): Publication sur le portail.
        vdn (bool): Publication sur VDN.
        poster_valide (bool): Indique si l'affiche est validée.
        description_poster_valide (str): Commentaires sur l'affiche.
        observations (str): Observations pour le bilan de l'atelier.
        series (UUID): Identifiant commun aux ateliers d'une même série.
        created_by (User): Utilisateur ayant créé l'atelier.
        updated_by (User): Dernier utilisateur ayant modifié l'atelier.
    """

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="workshops",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    date = models.DateField(db_index=True)
    date_end = models.DateField(null=True, blank=True, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    series = models.UUIDField(
        null=True,
        blank=True,
        editable=False,
        db_index=True,
        verbose_name="Série",
        help_text="Identifiant commun aux ateliers créés ensemble.",
    )
    series_index = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Position dans la série",
    )
    poster_required = models.BooleanField(db_index=True)
    image = models.ImageField(
        upload_to=workshop_image_upload_to,
        null=True,
        blank=True,
        validators=[
            validate_image_extension,
            validate_image_size,
            validate_image_content,
        ],
    )
    number_registered = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        db_index=True,
        validators=[MinValueValidator(0)],
    )
    number_attendees = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    class_welcome = models.BooleanField(default=False, db_index=True)
    instagram = models.BooleanField(default=False, null=True, db_index=True)
    facebook = models.BooleanField(default=False, null=True, db_index=True)
    mail = models.BooleanField(default=False, null=True, db_index=True)
    portail = models.BooleanField(default=False, null=True, db_index=True)
    vdn = models.BooleanField(default=False, null=True, db_index=True)
    poster_valide = models.BooleanField(default=False, null=True)
    description_poster_valide = models.TextField(null=True, blank=True)
    observations = models.TextField(
        null=True, blank=True, verbose_name="Observations"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Créé le"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Modifié le"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Créé par",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Modifié par",
    )

    class Meta:
        verbose_name = "Atelier"
        verbose_name_plural = "Ateliers"
        ordering = ["-date"]
        indexes = [
            models.Index(
                fields=["date", "class_welcome"],
                name="idx_workshop_date_class",
            ),
            models.Index(fields=["location", "date"], name="idx_workshop_loc_date"),
            models.Index(
                fields=["date", "number_registered"],
                name="idx_workshop_date_registered",
            ),
        ]

    def __str__(self):
        """Retourner une représentation textuelle de l'atelier.

        Returns:
            str: Le nom de l'atelier.
        """
        return self.name

    def clean(self):
        """Vérifier les contraintes du modèle.

        Vérifie que :
        - Le nom contient au moins une lettre ou un chiffre
        - La date de fin n'est pas antérieure à la date de début
        - L'heure de fin n'est pas antérieure à l'heure de début

        Raises:
            ValidationError: Si les contraintes ne sont pas respectées.
        """
        if self.name and not normalize_workshop_name(self.name):
            raise ValidationError(
                {
                    "name": (
                        "Le nom de l'atelier doit contenir au moins une "
                        "lettre ou un chiffre."
                    )
                }
            )

        # Valider que la date de fin n'est pas antérieure à la date de début
        if self.date_end and self.date_end < self.date:
            raise ValidationError(
                "La date de fin ne peut pas être antérieure à la date "
                "de début."
            )

        # Valider que l'heure de fin n'est pas antérieure à l'heure de début
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValidationError(
                "L'heure de fin ne peut pas être antérieure à l'heure "
                "de début."
            )
