# Scripts Utilitaires 🛠️

Ce répertoire contient des scripts utilitaires pour le développement et la maintenance du projet.

## pre_push_check.py

Script de vérification à exécuter avant de push le code. Il effectue automatiquement :
- Exécution des tests Django
- Vérification des migrations
- Exécution des hooks pre-commit (black, flake8, isort)

### Utilisation

```bash
# Depuis la racine du projet
python scripts/pre_push_check.py
```

Le script affichera également une checklist manuelle des points à vérifier qui ne peuvent pas être automatisés.

### Installation des dépendances

```bash
pip install pre-commit pip-audit
pre-commit install
```
