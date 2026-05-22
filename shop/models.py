"""Modèles de données pour l'application shop.

Ce module définit les modèles de données pour la gestion des catégories,
produits, structures et réservations dans l'application shop.
"""

from django.db import models, transaction
from django.db.models import F, Q

from app.validators import validate_image_extension


class Category(models.Model):
    """Modèle pour les catégories de produits.

    Une catégorie permet de regrouper des produits similaires pour
    faciliter leur organisation et leur recherche.
    """

    name = models.CharField(max_length=100, db_index=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]

    def __str__(self):
        """Retourne le nom de la catégorie.

        Returns:
            str: Le nom de la catégorie.
        """
        return self.name


class Product(models.Model):
    """Modèle pour les produits disponibles à la réservation.

    Un produit représente un article qui peut être réservé par une structure.
    Il possède une quantité disponible, une description, une catégorie et
    peut être temporairement désactivé via son statut.
    """

    name = models.CharField(max_length=100, db_index=True)
    quantity = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    image = models.ImageField(
        upload_to="product_images", null=True, blank=True,
        validators=[validate_image_extension]
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ["name"]

    def __str__(self):
        """Retourne le nom du produit.

        Returns:
            str: Le nom du produit.
        """
        return self.name

    def is_available_for_dates(self, start_date, end_date):
        """Vérifier la disponibilité du produit pour une période donnée.

        Args:
            start_date (datetime.date): Date de début de la période.
            end_date (datetime.date): Date de fin de la période.

        Returns:
            bool: True si le produit est disponible, False sinon.
        """
        overlapping_reservations = self.reservations.filter(
            Q(start_date__range=(start_date, end_date))
            | Q(end_date__range=(start_date, end_date))
            | Q(start_date__lte=start_date, end_date__gte=end_date),
            is_approved=True
        )
        return not overlapping_reservations.exists()

    def reserve(self, reservation_quantity):
        Product.objects.filter(pk=self.pk, quantity__gte=reservation_quantity).update(
            quantity=F("quantity") - reservation_quantity
        )
        self.refresh_from_db()

    def cancel_reservation(self, reservation_quantity):
        Product.objects.filter(pk=self.pk).update(
            quantity=F("quantity") + reservation_quantity
        )
        self.refresh_from_db()


class Structure(models.Model):
    """Modèle pour les structures qui peuvent effectuer des réservations."""

    name = models.CharField(max_length=100, db_index=True)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    email = models.EmailField()
    zip_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100)
    color = models.CharField(blank=True, max_length=20)
    image = models.ImageField(
        upload_to="structure_images", null=True, blank=True,
        validators=[validate_image_extension]
    )
    valid = models.BooleanField(default=True, db_index=True)
    is_registered = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Structure"
        verbose_name_plural = "Structures"
        ordering = ["name"]

    def __str__(self):
        """Retourne le nom de la structure.

        Returns:
            str: Le nom de la structure.
        """
        return self.name


class Reservation(models.Model):
    """Modèle pour les réservations de produits.

    Une réservation lie un produit à une structure pour une période donnée,
    avec une quantité spécifique. Elle peut être approuvée ou annulée
    par les administrateurs.
    """

    # Choix pour les raisons de désapprobation
    DISAPPROVAL_REASONS = [
        ('error', 'Erreur dans la demande'),
        ('conflict', 'Réservation en attente soumise avant celle-ci'),
        ('unavailable', 'Produit non disponible'),
        ('other', 'Autre raison'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reservations")
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(db_index=True)
    structure = models.ForeignKey(Structure, on_delete=models.CASCADE, related_name="reservations")
    quantity = models.PositiveIntegerField()
    is_approved = models.BooleanField(default=False, db_index=True)
    is_rejected = models.BooleanField(default=False, db_index=True)
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name="Rappel envoyé",
        help_text="Indique si le rappel J-1 a été envoyé pour cette réservation",
        db_index=True
    )
    deposit_time = models.TimeField(null=True)
    pickup_time = models.TimeField(null=True)
    description = models.TextField(null=True, blank=True)
    disapproval_reason = models.CharField(
        max_length=20,
        choices=DISAPPROVAL_REASONS,
        null=True,
        blank=True,
        verbose_name="Raison de désapprobation",
        db_index=True
    )
    disapproval_comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Commentaire de désapprobation"
    )

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["start_date", "end_date"], name="idx_reservation_dates"),
        ]

    def __str__(self):
        """Retourne une description de la réservation.

        Returns:
            str: Une chaîne décrivant la réservation avec le produit,
                la structure et les dates.
        """
        return (
            f"{self.product.name} - {self.structure.name} "
            f"({self.start_date} - {self.end_date})"
        )

    def approve_reservation(self):
        """Approuve la réservation.

        Cette méthode marque la réservation comme approuvée.
        """
        if self.is_approved:
            return
        with transaction.atomic():
            self.is_approved = True
            self.save(update_fields=["is_approved"])
            self.product.reserve(self.quantity)

    def cancel_reservation(self):
        """Annule la réservation.

        Cette méthode marque la réservation comme non approuvée.
        """
        if not self.is_approved:
            return
        self.is_approved = False
        self.save()
        self.product.cancel_reservation(self.quantity)

    def reject_reservation(self, reason=None, comment=None):
        """Rejette la réservation.

        Cette méthode marque la réservation comme rejetée.

        Args:
            reason (str): Raison du rejet.
            comment (str): Commentaire du rejet.
        """
        self.is_rejected = True
        self.is_approved = False
        if reason:
            self.disapproval_reason = reason
        if comment:
            self.disapproval_comment = comment
        self.save()
