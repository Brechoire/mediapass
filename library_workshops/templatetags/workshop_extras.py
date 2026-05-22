from django import template


register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Template filter pour accéder aux éléments d'un dictionnaire par clé"""
    return dictionary.get(key)
