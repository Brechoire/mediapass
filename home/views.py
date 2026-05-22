"""Vues pour l'application home."""

import logging
import os
import shutil
import zipfile
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect

from accounts.utils import is_staff_or_superuser, group_required
from shop.models import Product

logger = logging.getLogger(__name__)


def is_superuser(user):
    """Vérifie si l'utilisateur est un superutilisateur.

    Args:
        user: L'utilisateur à vérifier.

    Returns:
        bool: True si l'utilisateur est un superutilisateur, False sinon.
    """
    return user.is_superuser


def index(request):
    """Affiche la page d'accueil.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page d'accueil rendue.
    """
    return render(request, "home/index.html")


def search(request):
    """Effectue une recherche dans les produits.

    Args:
        request: La requête HTTP contenant les termes de recherche.

    Returns:
        HttpResponse: La page des résultats de recherche.
    """
    query = request.GET.get("q")
    if query:
        results = Product.objects.select_related("category").filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
        paginator = Paginator(results, 20)
        page_number = request.GET.get("page")
        results = paginator.get_page(page_number)
    else:
        results = []
    return render(
        request, "home/search.html", {
            "results": results, "query": query,
            "page_obj": results if results else None,
        }
    )


def legal_information(request):
    """Affiche les informations légales.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page des informations légales.
    """
    return render(request, "home/legalinformation.html")


@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
@csrf_protect
def backup_database(request):
    """Crée une sauvegarde de la base de données.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: Le fichier de sauvegarde à télécharger.
    """
    db_path = settings.DATABASES["default"]["NAME"]
    backup_path = os.path.join(settings.MEDIA_ROOT, "db_backup.sqlite3")

    try:
        shutil.copyfile(db_path, backup_path)
        with open(backup_path, "rb") as fh:
            response = HttpResponse(
                fh.read(), content_type="application/x-sqlite3"
            )
            response["Content-Disposition"] = (
                "attachment; filename=db_backup.sqlite3"
            )
            return response
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)


@login_required(login_url="login")
@user_passes_test(is_superuser)
@csrf_protect
def backup_media_folders(request):
    """Crée une sauvegarde des dossiers média.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: Le fichier de sauvegarde à télécharger.
    """
    media_root = settings.MEDIA_ROOT
    folders_to_backup = [
        "ateliers_images",
        "product_images",
        "structure_images",
    ]
    backup_path = os.path.join(media_root, "media_backup.zip")

    try:
        with zipfile.ZipFile(backup_path, "w") as zipf:
            for folder in folders_to_backup:
                folder_path = os.path.join(media_root, folder)
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(
                            file_path, os.path.relpath(file_path, media_root)
                        )

        with open(backup_path, "rb") as fh:
            response = HttpResponse(fh.read(), content_type="application/zip")
            response["Content-Disposition"] = (
                "attachment; filename=media_backup.zip"
            )
            return response
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)


@login_required(login_url="login")
@user_passes_test(is_superuser)
@csrf_protect
def backup_all(request):
    """Crée une sauvegarde complète (base de données et dossiers média).

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: Un fichier zip contenant toutes les sauvegardes.
    """
    try:
        # Créer un dossier temporaire pour les sauvegardes
        backup_dir = os.path.join(settings.MEDIA_ROOT, "backup_temp")
        os.makedirs(backup_dir, exist_ok=True)

        # Sauvegarder la base de données
        db_path = settings.DATABASES["default"]["NAME"]
        db_backup_path = os.path.join(backup_dir, "db_backup.sqlite3")
        shutil.copyfile(db_path, db_backup_path)

        # Sauvegarder les dossiers média
        folders_to_backup = [
            "ateliers_images",
            "product_images",
            "structure_images",
        ]

        # Créer un zip contenant tout
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_zip_path = os.path.join(
            settings.MEDIA_ROOT, f"backup_complet_{timestamp}.zip"
        )

        with zipfile.ZipFile(final_zip_path, "w") as zipf:
            # Ajouter la base de données
            zipf.write(db_backup_path, "database/db_backup.sqlite3")

            # Ajouter les dossiers média
            for folder in folders_to_backup:
                folder_path = os.path.join(settings.MEDIA_ROOT, folder)
                if os.path.exists(folder_path):
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join(
                                "media",
                                folder,
                                os.path.relpath(file_path, folder_path),
                            )
                            zipf.write(file_path, arcname)

        # Nettoyer le dossier temporaire
        shutil.rmtree(backup_dir)

        # Préparer la réponse
        with open(final_zip_path, "rb") as fh:
            response = HttpResponse(fh.read(), content_type="application/zip")
            response["Content-Disposition"] = (
                f"attachment; filename=backup_complet_{timestamp}.zip"
            )

        # Supprimer le zip après l'avoir envoyé
        os.remove(final_zip_path)

        return response

    except Exception as e:
        logger.error("Erreur lors de la sauvegarde complète : %s", str(e))
        return HttpResponse(
            "Erreur lors de la sauvegarde complète", status=500
        )



