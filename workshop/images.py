"""Optimisation des images téléversées pour les ateliers.

Les images sont redimensionnées si nécessaire, réencodées avec un poids
raisonnable et débarrassées de leurs métadonnées (dont les données EXIF).
Les GIF sont laissés intacts pour ne pas casser une éventuelle animation.
"""

import io
import logging
import os

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1920
JPEG_QUALITY = 85

OPTIMIZABLE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
OPTIMIZABLE_FORMATS = {"PNG", "JPEG", "WEBP"}


def optimize_workshop_image(uploaded_file):
    """Retourne une version optimisée du fichier, ou le fichier d'origine.

    L'optimisation échoue silencieusement : un problème Pillow ne doit
    jamais empêcher l'enregistrement d'un atelier déjà validé.
    """
    if not uploaded_file or not getattr(uploaded_file, "name", ""):
        return uploaded_file

    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension not in OPTIMIZABLE_EXTENSIONS:
        return uploaded_file

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
        image_format = (image.format or "").upper()
        if image_format not in OPTIMIZABLE_FORMATS:
            uploaded_file.seek(0)
            return uploaded_file

        image = ImageOps.exif_transpose(image)
        resized = max(image.size) > MAX_DIMENSION
        if resized:
            resampling = getattr(Image, "Resampling", Image)
            image.thumbnail(
                (MAX_DIMENSION, MAX_DIMENSION), resampling.LANCZOS
            )

        save_kwargs = {"optimize": True}
        if image_format == "JPEG":
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            save_kwargs.update(quality=JPEG_QUALITY, progressive=True)
        elif image_format == "PNG":
            if image.mode == "P":
                image = image.convert("RGBA")
        else:  # WEBP
            if image.mode not in ("RGB", "RGBA"):
                has_alpha = "A" in image.getbands()
                image = image.convert("RGBA" if has_alpha else "RGB")
            save_kwargs.update(quality=JPEG_QUALITY, method=6)

        output = io.BytesIO()
        image.save(output, format=image_format, **save_kwargs)
        data = output.getvalue()

        original_bytes = getattr(uploaded_file, "size", None)
        if (
            not resized
            and original_bytes is not None
            and len(data) >= original_bytes
        ):
            uploaded_file.seek(0)
            return uploaded_file

        optimized = ContentFile(data, name=uploaded_file.name)
        content_type = getattr(uploaded_file, "content_type", None)
        if content_type:
            optimized.content_type = content_type
        return optimized
    except Exception:
        logger.warning(
            "Optimisation d'image ignorée pour %s",
            getattr(uploaded_file, "name", "fichier inconnu"),
            exc_info=True,
        )
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return uploaded_file
