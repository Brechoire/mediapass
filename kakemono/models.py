from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.validators import validate_image_extension


def validate_future_date(value):
    if value < timezone.now().date():
        raise ValidationError("La date ne peut pas être dans le passé.")


class Kakemono(models.Model):
    title = models.CharField(max_length=200, verbose_name="Titre", db_index=True)
    image = models.ImageField(upload_to="kakemonos/", verbose_name="Image",
                               validators=[validate_image_extension])
    description = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Dernière modification"
    )
    is_available = models.BooleanField(default=True, verbose_name="Disponible", db_index=True)

    class Meta:
        verbose_name = "Kakémono"
        verbose_name_plural = "Kakémonos"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def is_reserved(self, start_date, end_date):
        return self.reservations.filter(
            models.Q(start_date__lte=end_date)
            & models.Q(end_date__gte=start_date),
            status="confirmed",
        ).exists()


class KakemonoReservation(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("confirmed", "Confirmée"),
        ("cancelled", "Annulée"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="kakemono_reservations",
        verbose_name="Utilisateur",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    kakemonos = models.ManyToManyField(
        Kakemono, related_name="reservations", verbose_name="Kakémonos"
    )
    start_date = models.DateField(
        validators=[validate_future_date], verbose_name="Date de début",
        db_index=True
    )
    end_date = models.DateField(
        validators=[validate_future_date], verbose_name="Date de fin",
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Statut",
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création",
        db_index=True
    )
    notes = models.TextField(
        blank=True, null=True, verbose_name="Notes (optionnel)"
    )

    class Meta:
        verbose_name = "Réservation de kakémono"
        verbose_name_plural = "Réservations de kakémonos"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            "Réservation de"
            f" {self.first_name} {self.last_name} ({self.get_status_display()})"
        )

    def clean(self):
        if (
            self.start_date
            and self.end_date
            and self.start_date > self.end_date
        ):
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
