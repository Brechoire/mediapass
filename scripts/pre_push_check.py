"""Script de vérification avant un push."""

import os
import subprocess
import sys
from typing import List, Tuple


def run_command(command: List[str]) -> Tuple[int, str, str]:
    """Exécute une commande et retourne son statut et sa sortie."""
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr


def main():
    """Exécute toutes les vérifications pre-push."""
    checks = [
        {
            "name": "Tests Django",
            "command": ["python", "manage.py", "test"],
            "error_msg": "❌ Certains tests ont échoué",
        },
        {
            "name": "Vérification des migrations",
            "command": ["python", "manage.py", "makemigrations", "--check"],
            "error_msg": "❌ Il y a des migrations non committées",
        },
        {
            "name": "Pre-commit hooks",
            "command": ["pre-commit", "run", "--all-files"],
            "error_msg": "❌ Les hooks pre-commit ont échoué",
        },
    ]

    print("🔍 Démarrage des vérifications pre-push...")

    failed = False
    for check in checks:
        print(f"\n⚡ Exécution de : {check['name']}")
        returncode, stdout, stderr = run_command(check["command"])

        if returncode != 0:
            print(check["error_msg"])
            print("📝 Détails :")
            print(stdout)
            print(stderr)
            failed = True
        else:
            print(f"✅ {check['name']} : OK")

    if failed:
        print(
            "\n❌ Certaines vérifications ont échoué. Veuillez corriger les"
            " erreurs avant de push."
        )
        sys.exit(1)
    else:
        print("\n✅ Toutes les vérifications sont passées !")
        print("\n📋 Checklist manuelle :")
        print("1. CHANGELOG.md mis à jour ?")
        print("2. Documentation à jour ?")
        print("3. Pas de données sensibles dans le code ?")
        print("4. Commits atomiques et bien nommés ?")


if __name__ == "__main__":
    # S'assurer qu'on est dans le répertoire racine du projet
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    main()
