from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Commune(models.Model):
    """Modèle pour représenter une commune"""
    
    name = models.CharField(
        max_length=100,
        verbose_name="Nom de la commune",
        unique=True
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
        verbose_name = "Commune"
        verbose_name_plural = "Communes"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Lieu(models.Model):
    """Modèle pour représenter un lieu de distribution dans une commune"""
    
    commune = models.ForeignKey(
        Commune,
        on_delete=models.CASCADE,
        related_name='lieux',
        verbose_name="Commune",
        db_index=True
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name="Nom du lieu"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description optionnelle du lieu"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Décochez pour désactiver ce lieu",
        db_index=True
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
        verbose_name = "Lieu"
        verbose_name_plural = "Lieux"
        ordering = ['commune__name', 'name']
        unique_together = ['commune', 'name']
    
    def __str__(self):
        return f"{self.commune.name} - {self.name}"


class CampagneDistribution(models.Model):
    """Modèle pour représenter une campagne de distribution"""
    
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('active', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ]
    
    name = models.CharField(
        max_length=200,
        verbose_name="Nom de la campagne",
        help_text="Ex: Quinzaine du conte, Festival d'été, etc."
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description de la campagne de distribution"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Statut",
        db_index=True
    )

    start_date = models.DateField(
        verbose_name="Date de début",
        help_text="Date de début de la campagne",
        db_index=True
    )

    end_date = models.DateField(
        verbose_name="Date de fin",
        help_text="Date de fin prévue de la campagne",
        db_index=True
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='campagnes_created',
        verbose_name="Créé par",
        db_index=True
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
        db_index=True
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification"
    )

    class Meta:
        verbose_name = "Campagne de distribution"
        verbose_name_plural = "Campagnes de distribution"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def total_lieux(self):
        """Retourne le nombre total de lieux dans cette campagne"""
        if hasattr(self, '_total_lieux'):
            return self._total_lieux
        return self.distributions.count()

    @property
    def lieux_distribues(self):
        """Retourne le nombre de lieux où la distribution a été effectuée"""
        if hasattr(self, '_lieux_distribues'):
            return self._lieux_distribues
        return self.distributions.filter(is_distributed=True).count()

    @property
    def progression(self):
        """Retourne le pourcentage de progression"""
        total = self.total_lieux
        if total == 0:
            return 0
        return round((self.lieux_distribues / total) * 100, 1)

    @property
    def is_completed(self):
        """Retourne True si la campagne est complète"""
        total = self.total_lieux
        return self.lieux_distribues == total and total > 0


class Distribution(models.Model):
    """Modèle pour représenter une distribution dans un lieu spécifique"""
    
    campagne = models.ForeignKey(
        CampagneDistribution,
        on_delete=models.CASCADE,
        related_name='distributions',
        verbose_name="Campagne",
        db_index=True
    )
    
    lieu = models.ForeignKey(
        Lieu,
        on_delete=models.CASCADE,
        related_name='distributions',
        verbose_name="Lieu",
        db_index=True
    )
    
    is_distributed = models.BooleanField(
        default=False,
        verbose_name="Distribué",
        help_text="Cochez si le flyer a été distribué dans ce lieu",
        db_index=True
    )
    
    distributed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='distributions_made',
        verbose_name="Distribué par"
    )
    
    distributed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de distribution"
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes",
        help_text="Notes optionnelles sur la distribution"
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
        verbose_name = "Distribution"
        verbose_name_plural = "Distributions"
        ordering = ['campagne', 'lieu__commune__name', 'lieu__name']
        unique_together = ['campagne', 'lieu']
    
    def __str__(self):
        return f"{self.campagne.name} - {self.lieu}"
    
    def save(self, *args, **kwargs):
        """Override save pour gérer la date de distribution"""
        if self.is_distributed and not self.distributed_at:
            self.distributed_at = timezone.now()
        elif not self.is_distributed:
            self.distributed_at = None
            self.distributed_by = None
        super().save(*args, **kwargs)
