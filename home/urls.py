"""Configuration des URLs pour l'application home."""

from django.urls import path

from .views import (
    backup_all,
    backup_database,
    backup_media_folders,
    index,
    legal_information,
    search,
)

urlpatterns = [
    path("", index, name="home"),
    path("recherche/", search, name="search"),
    path("mentions-legales/", legal_information, name="legalinformation"),
    path("backup/database/", backup_database, name="backup_database"),
    path("backup/media/", backup_media_folders, name="backup_media"),
    path("backup/all/", backup_all, name="backup_all"),
]
