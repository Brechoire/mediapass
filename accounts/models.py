"""Modèles de profils médiathèques — app accounts (source de vérité)."""

from django.conf import settings
from django.db import models


class LibraryProfile(models.Model):
    """Fiche d'une médiathèque : identité et informations pratiques (éditable par la médiathèque)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_profile",
        verbose_name="Compte médiathèque",
    )
    name = models.CharField("Nom de la médiathèque", max_length=150)
    image = models.ImageField(
        "Logo", upload_to="newsletter/libraries/", null=True, blank=True
    )
    banner = models.ImageField(
        "Bannière",
        upload_to="newsletter/banners/",
        null=True,
        blank=True,
        help_text="Image large pour l'en-tête newsletter (ex. 1200×400)",
    )
    description = models.TextField("Description", blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    opening_hours = models.TextField(
        "Horaires d'ouverture",
        blank=True,
        help_text="Une ligne par jour, ex. « Lundi : 14h - 18h »",
    )
    closures = models.TextField(
        "Fermetures exceptionnelles", blank=True, help_text="Une fermeture par ligne"
    )
    website = models.URLField("Site web", max_length=255, blank=True)
    facebook_url = models.URLField("Facebook", max_length=255, blank=True)
    instagram_url = models.URLField("Instagram", max_length=255, blank=True)
    youtube_url = models.URLField("YouTube", max_length=255, blank=True)
    tiktok_url = models.URLField("TikTok", max_length=255, blank=True)
    x_url = models.URLField("X / Twitter", max_length=255, blank=True)
    updated_at = models.DateTimeField("Modification", auto_now=True)

    class Meta:
        verbose_name = "Fiche médiathèque"
        verbose_name_plural = "Fiches médiathèques"

    def __str__(self):
        return self.name

    @property
    def hours_lines(self):
        return [l.strip() for l in self.opening_hours.splitlines() if l.strip()]

    @property
    def closure_lines(self):
        return [l.strip() for l in self.closures.splitlines() if l.strip()]
