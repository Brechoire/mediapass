"""Module de formulaires pour l'application accounts.

Ce module contient les formulaires personnalisés pour la gestion des
comptes utilisateurs.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """Formulaire de connexion personnalisé avec option 'Rester connecté'."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Nom d'utilisateur",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Mot de passe",
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label="Rester connecté",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
