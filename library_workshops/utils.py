def filter_owned(queryset, user, field='created_by'):
    if user.is_superuser:
        return queryset
    return queryset.filter(**{field: user})


def filter_location_owned(queryset, user, field='user'):
    if user.is_superuser:
        return queryset
    return queryset.filter(**{field: user})
