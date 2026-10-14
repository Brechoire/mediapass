"""Modèles de données pour l'application documents."""

from django.db import models

from .validators import (
    document_upload_to,
    validate_document_content,
    validate_document_extension,
    validate_document_size,
)


class DocumentCategory(models.Model):
    """Catégorie permettant d'organiser les documents (règlements, etc.)."""

    ICON_CHOICES = [
        ("bx-folder", "Dossier"),
        ("bx-file", "Document"),
        ("bx-file-blank", "Formulaire"),
        ("bx-book", "Règlement / Livret"),
        ("bx-edit", "Inscription / Édition"),
        ("bx-calendar", "Agenda / Dates"),
        ("bx-image", "Communication visuelle"),
        ("bx-info-circle", "Information"),
    ]

    name = models.CharField(
        max_length=100, unique=True, verbose_name="Nom", db_index=True
    )
    description = models.CharField(
        max_length=255, blank=True, verbose_name="Description"
    )
    icon = models.CharField(
        max_length=50,
        choices=ICON_CHOICES,
        default="bx-folder",
        verbose_name="Icône",
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Ordre d'affichage"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Catégorie de document"
        verbose_name_plural = "Catégories de documents"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Document(models.Model):
    """Document PDF téléchargeable, publié ou non sur la page publique."""

    title = models.CharField(
        max_length=200, verbose_name="Titre", db_index=True
    )
    description = models.TextField(blank=True, verbose_name="Description")
    file = models.FileField(
        upload_to=document_upload_to,
        verbose_name="Fichier PDF",
        validators=[
            validate_document_extension,
            validate_document_size,
            validate_document_content,
        ],
    )
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        related_name="documents",
        null=True,
        blank=True,
        verbose_name="Catégorie",
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Ordre d'affichage"
    )
    is_published = models.BooleanField(
        default=True, db_index=True, verbose_name="Publié"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["display_order", "title"]

    def __str__(self):
        return self.title
