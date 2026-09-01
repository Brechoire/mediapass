"""Validateurs d'images sécurisés — newsletter + médiathèques."""

import os
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError

# Allow-list stricte : pas de SVG / AVIF (vecteur / XSS)
ALLOWED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
# FileExtensionValidator attend les extensions sans point (impl Django utilise suffix[1:])
ALLOWED_IMAGE_EXTENSIONS_NODOT = ["png", "jpg", "jpeg", "gif", "webp"]
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "GIF", "WEBP"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo
MAX_IMAGE_PIXELS = 25_000_000  # 25 Mpx


def validate_image_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Format d'image non supporté. Formats acceptés : "
            f"{', '.join(ALLOWED_IMAGE_EXTENSIONS)}."
        )


def validate_image_size(value):
    """Rejette les fichiers > 5 Mo."""
    size = getattr(value, "size", None)
    if size is not None and size > MAX_IMAGE_SIZE:
        raise ValidationError("Image trop volumineuse (maximum 5 Mo).")


def validate_image_content(value):
    """Valide le contenu réel de l'image : taille, format Pillow, dimensions, pas de SVG/XML."""
    # Taille
    size = getattr(value, "size", None)
    if size is not None and size > MAX_IMAGE_SIZE:
        raise ValidationError("Image trop volumineuse (maximum 5 Mo).")

    # Header anti-SVG / XML
    try:
        value.seek(0)
        header = value.read(512)
        value.seek(0)
    except Exception:
        header = b""
    if header:
        stripped = header.lstrip().lower()
        if stripped.startswith(b"<?xml") or stripped.startswith(b"<svg"):
            raise ValidationError("Image invalide")
        # détection générique <svg dans les premiers octets
        if b"<svg" in stripped[:200]:
            raise ValidationError("Image invalide")

    # Validation Pillow
    try:
        from PIL import Image
    except ImportError:
        # Pillow non disponible : on ne peut pas vérifier plus finement
        value.seek(0)
        return

    try:
        value.seek(0)
        img = Image.open(value)
        img.verify()
        value.seek(0)
        img = Image.open(value)
        # format
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("Image invalide")
        width, height = img.size
        if width * height > MAX_IMAGE_PIXELS:
            raise ValidationError("Image invalide")
        # charge un peu pour détecter image tronquée
        img.load()
        value.seek(0)
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("Image invalide")


# ---------------------------------------------------------------------------
# Helpers upload_to sécurisés (randomisation + allow-list)
# ---------------------------------------------------------------------------

def _validated_upload_to(subdir: str, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Format d'image non supporté. Formats acceptés : "
            f"{', '.join(ALLOWED_IMAGE_EXTENSIONS)}."
        )
    return f"{subdir}/{uuid.uuid4().hex}{ext}"


def newsletter_image_upload_to(instance, filename):
    return _validated_upload_to("newsletter/blocks", filename)


def library_image_upload_to(instance, filename):
    return _validated_upload_to("newsletter/libraries", filename)


def library_banner_upload_to(instance, filename):
    return _validated_upload_to("newsletter/banners", filename)
