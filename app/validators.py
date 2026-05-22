import os

from django.core.exceptions import ValidationError


def validate_image_extension(value):
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.avif']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f"Format d'image non supporté. Formats acceptés : "
            f"{', '.join(allowed_extensions)}."
        )
