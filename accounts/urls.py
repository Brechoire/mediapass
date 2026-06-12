"""Configuration des URLs pour l'application accounts."""
from django.urls import path

from .views import CustomLoginView, logout_view

urlpatterns = [
    path(
        "connexion/",
        CustomLoginView.as_view(),
        name="login",
    ),
    path("deconnexion/", logout_view, name="logout"),
]
