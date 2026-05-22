"""Services pour la gestion des ateliers.

Ce module fournit des fonctions utilitaires pour la gestion des ateliers,
notamment le traitement des images et l'envoi de notifications.
"""

import random
import re
import string
import unicodedata
from os.path import splitext


def clean_filename(filename):
    """Nettoie le nom de fichier en remplaçant les caractères spéciaux.

    Args:
        filename (str): Le nom de fichier à nettoyer.

    Returns:
        str: Le nom de fichier nettoyé.
    """
    # Normaliser les caractères Unicode (décomposer les accents)
    filename = unicodedata.normalize("NFKD", filename)
    # Encoder en ASCII en ignorant les caractères non-ASCII
    filename = filename.encode("ASCII", "ignore").decode("ASCII")
    # Remplacer les caractères non-alphanumériques par des tirets
    filename = re.sub(r"[^a-zA-Z0-9.]", "-", filename)
    return filename


def generate_random_filename(filename):
    """Générer un nom de fichier aléatoire.

    Cette fonction prend un nom de fichier en entrée et génère un nouveau
    nom aléatoire tout en conservant l'extension du fichier d'origine.
    Cela évite les collisions de noms lors du téléchargement.

    Args:
        filename (str): Le nom d'origine du fichier.

    Returns:
        str: Un nom de fichier aléatoire avec l'extension d'origine.
    """
    try:
        # Nettoyer le nom de fichier
        clean_name = clean_filename(filename)

        # Séparer le nom et l'extension du fichier
        name, extension = splitext(clean_name)

        # Si l'extension est vide ou invalide, extraire depuis le nom original
        if not extension:
            _, extension = splitext(filename)

        # S'assurer que l'extension est en minuscules
        extension = extension.lower()

        # Générer une chaîne aléatoire de 10 caractères
        random_string = "".join(
            random.choice(string.ascii_lowercase) for i in range(10)
        )

        # Combiner la chaîne aléatoire avec l'extension
        new_filename = f"{random_string}{extension}"

        return new_filename
    except Exception as e:
        # En cas d'erreur, retourner un nom par défaut
        return f"image_{random.randint(1000, 9999)}.jpg"
