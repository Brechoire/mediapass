from django import template
from django.template.defaultfilters import date as date_filter
from django.utils import timezone

register = template.Library()


@register.filter
def days_until(value):
    """Retourne le nombre de jours entre aujourd'hui et la date donnée.

    Format: J+3, J-1, J0, etc.
    """
    if not value:
        return ""
    today = timezone.now().date()
    if hasattr(value, "date"):
        value = value.date()
    diff = (value - today).days
    if diff > 0:
        return f"J+{diff}"
    elif diff < 0:
        return f"J{diff}"
    return "J0"
