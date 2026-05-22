"""Configuration des URLs pour l'application accounts.

Ce module définit les routes URL pour l'authentification des utilisateurs,
notamment la connexion et la déconnexion.
"""

from django.urls import path
from django.contrib.auth import views as auth_views

from .views import logout_view

urlpatterns = [
    path(
        "connexion/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("deconnexion/", logout_view, name="logout"),
]
