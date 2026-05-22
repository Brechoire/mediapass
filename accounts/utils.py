from django.contrib.auth.decorators import user_passes_test


def is_staff_or_superuser(user):
    """Vérifie si l'utilisateur est staff ou superuser."""
    return user.is_staff or user.is_superuser


def group_required(*group_names):
    """Décorateur qui vérifie l'appartenance aux groupes spécifiés.

    Args:
        *group_names: Liste des noms de groupes à vérifier.
    """
    def in_groups(user):
        if user.is_authenticated:
            if bool(user.groups.filter(name__in=group_names)) or user.is_superuser:
                return True
        return False
    return user_passes_test(in_groups)


def is_staff_or_superuser_or_in_comm_group(user):
    """Vérifie si l'utilisateur est staff, superuser ou dans le groupe communication."""
    is_comm = user.groups.filter(name="communication").exists()
    return user.is_staff or user.is_superuser or is_comm
