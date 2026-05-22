"""Modèles de données pour la gestion des ateliers."""

from django.core.exceptions import ValidationError
from django.db import models

from app.validators import validate_image_extension


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
    """

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="workshops")
    name = models.CharField(max_length=255)
    date = models.DateField(db_index=True)
    date_end = models.DateField(null=True, blank=True, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    poster_required = models.BooleanField(db_index=True)
    image = models.ImageField(
        upload_to="ateliers_images", null=True, blank=True,
        validators=[validate_image_extension]
    )
    number_registered = models.IntegerField(default=0, null=True, blank=True, db_index=True)
    number_attendees = models.IntegerField(default=0, null=True, blank=True)
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

    class Meta:
        verbose_name = "Atelier"
        verbose_name_plural = "Ateliers"
        ordering = ["-date"]

    def __str__(self):
        """Retourner une représentation textuelle de l'atelier.

        Returns:
            str: Le nom de l'atelier.
        """
        return self.name

    def clean(self):
        """Vérifier les contraintes du modèle.

        Vérifie que :
        - La date de fin n'est pas antérieure à la date de début
        - L'heure de fin n'est pas antérieure à l'heure de début

        Raises:
            ValidationError: Si les contraintes ne sont pas respectées.
        """
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
