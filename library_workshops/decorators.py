"""Décorateurs pour la gestion des permissions de la médiathèque."""

from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse


def mediatheque_member_required(view_func):
    """
    Décorateur qui vérifie si l'utilisateur est membre du groupe 'mediatheque'.
    Redirige vers la page de connexion ou d'accès refusé sinon.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.groups.filter(name='mediatheque').exists():
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def mediatheque_member_required_json(view_func):
    """
    Décorateur similaire mais retourne une réponse JSON en cas d'erreur.
    Utile pour les endpoints AJAX/HTMX.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentification requise'}, status=401)
        if not request.user.groups.filter(name='mediatheque').exists():
            return JsonResponse({'error': 'Accès refusé'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

