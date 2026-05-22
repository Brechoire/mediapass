"""Module de vues pour l'application accounts.

Ce module contient les vues pour gérer l'authentification des utilisateurs,
notamment la connexion et la déconnexion.
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST


@user_passes_test(lambda u: not u.is_authenticated, login_url="home")
def process_login(request):
    """Gère le processus de connexion des utilisateurs.

    Cette vue vérifie les informations d'identification de l'utilisateur
    et le connecte s'il est authentifié avec succès.

    Args:
        request: La requête HTTP contenant les données du formulaire.

    Returns:
        HttpResponse: Redirection vers la page d'accueil si connexion réussie,
            ou affichage du formulaire de connexion avec les erreurs.
    """
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


@require_POST
@csrf_protect
def logout_view(request):
    """Déconnecte l'utilisateur et le redirige vers la page d'accueil.

    Cette vue termine la session de l'utilisateur et le redirige vers
    la page d'accueil du site.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: Redirection vers la page d'accueil après déconnexion.
    """
    logout(request)
    return redirect("home")
