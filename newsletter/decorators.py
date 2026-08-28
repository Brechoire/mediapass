"""Décorateurs d'accès pour l'application newsletter."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def _is_communication(user):
    return user.is_superuser or user.groups.filter(name="communication").exists()


def communication_required(view_func):
    """Accès réservé au groupe « communication » et aux superusers."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not _is_communication(request.user):
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def fiche_edit_required(view_func):
    """Édition de fiche : superuser/communication (toutes) ou la médiathèque propriétaire."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if _is_communication(request.user):
            return view_func(request, *args, **kwargs)
        if not request.user.groups.filter(name="mediatheque").exists():
            return redirect("home")
        profile_id = kwargs.get("profile_id")
        if profile_id is not None:
            from accounts.models import LibraryProfile

            profile = LibraryProfile.objects.filter(pk=profile_id).first()
            if profile is None or profile.user_id != request.user.pk:
                return redirect("home")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def mediatheque_required(view_func):
    """Accès réservé aux membres du groupe « médiathèque » (fiche personnelle)."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.groups.filter(name="mediatheque").exists():
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
