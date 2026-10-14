"""Configuration des URLs de l'application documents."""

from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path("gestion/", views.document_manage, name="document_manage"),
    path("gestion/nouveau/", views.document_create, name="document_create"),
    path(
        "gestion/<int:pk>/modifier/",
        views.document_update,
        name="document_update",
    ),
    path(
        "gestion/<int:pk>/supprimer/",
        views.document_delete,
        name="document_delete",
    ),
    path(
        "gestion/categories/nouvelle/",
        views.documentcategory_create,
        name="documentcategory_create",
    ),
    path(
        "gestion/categories/<int:pk>/modifier/",
        views.documentcategory_update,
        name="documentcategory_update",
    ),
    path(
        "gestion/categories/<int:pk>/supprimer/",
        views.documentcategory_delete,
        name="documentcategory_delete",
    ),
]
