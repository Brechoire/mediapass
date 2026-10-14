"""Validateurs d'upload pour les documents PDF.

Seuls les fichiers PDF sont acceptés : extension contrôlée, taille limitée
et vérification des octets d'en-tête (%PDF-) pour rejeter les faux fichiers.
"""

import os
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError

ALLOWED_DOCUMENT_EXTENSIONS = [".pdf"]
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 Mo
PDF_MAGIC = b"%PDF-"


def validate_document_extension(value):
    """Vérifie que le fichier uploadé possède bien l'extension .pdf."""
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            "Format de fichier non supporté. Seuls les fichiers PDF sont "
            "acceptés."
        )


def validate_document_size(value):
    """Rejette les fichiers de plus de 10 Mo."""
    size = getattr(value, "size", None)
    if size is not None and size > MAX_DOCUMENT_SIZE:
        raise ValidationError(
            "Fichier trop volumineux (maximum 10 Mo)."
        )


def validate_document_content(value):
    """Vérifie l'en-tête réel du fichier : un PDF commence par %PDF-."""
    size = getattr(value, "size", None)
    if size is not None and size > MAX_DOCUMENT_SIZE:
        raise ValidationError(
            "Fichier trop volumineux (maximum 10 Mo)."
        )

    try:
        value.seek(0)
        header = value.read(1024)
        value.seek(0)
    except Exception:
        header = b""

    stripped = header.lstrip(b"\x00\xef\xbb\xbf \t\r\n")
    if not stripped.startswith(PDF_MAGIC):
        raise ValidationError("Fichier PDF invalide.")


def document_upload_to(instance, filename):
    """Nom de fichier randomisé pour éviter les collisions et les devinettes."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            "Format de fichier non supporté. Seuls les fichiers PDF sont "
            "acceptés."
        )
    return f"documents/{uuid.uuid4().hex}{ext}"
