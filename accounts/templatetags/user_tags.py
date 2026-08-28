from django import template

register = template.Library()


@register.filter
def has_group(user, group_name):
    if not user.is_authenticated:
        return False
    cache = getattr(user, "_group_names_cache", None)
    if cache is None:
        cache = frozenset(user.groups.values_list("name", flat=True))
        user._group_names_cache = cache
    return group_name in cache
