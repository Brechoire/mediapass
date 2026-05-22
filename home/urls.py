"""Configuration des URLs pour l'application home."""

from django.urls import path

from .views import (
    backup_all,
    backup_database,
    backup_media_folders,
    handler404,
    index,
    legal_information,
    save,
    search,
)

urlpatterns = [
    path("", index, name="home"),
    path("", handler404, name="handler404"),
    path("recherche/", search, name="search"),
    path("mentions-legales/", legal_information, name="legalinformation"),
    path("backup/database/", backup_database, name="backup_database"),
    path("sauvegarde", save, name="save"),
    path("backup/media/", backup_media_folders, name="backup_media"),
    path("backup/all/", backup_all, name="backup_all"),
]
