# 🎫 MediaPass Reservation System

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/Django-4.2.2-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Un système de réservation moderne et complet pour la gestion des équipements multimédias, des ateliers et des kakemonos, développé pour la Communauté de Communes Sud-Avesnois.

## 📋 Table des Matières
- [✨ Fonctionnalités](#-fonctionnalités)
- [📋 Prérequis](#-prérequis)
- [🚀 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [🏗️ Structure du Projet](#️-structure-du-projet)
- [🔐 Sécurité](#-sécurité)
- [📊 Fonctionnalités Détaillées](#-fonctionnalités-détaillées)
- [🔧 Technologies Utilisées](#-technologies-utilisées)
- [👥 Contribution](#-contribution)
- [📝 License](#-license)

## ✨ Fonctionnalités

### 🎯 Fonctionnalités Principales
- 🔐 Système d'authentification utilisateur complet avec gestion des rôles
- 📱 Interface responsive et moderne avec Bootstrap 5
- 📅 Gestion complète des réservations d'équipements multimédias
- 🎨 Gestion des ateliers avec inscriptions et planification
- 🖼️ Gestion des kakemonos (affiches/banderoles)
- 📧 Notifications par email automatiques
- 📊 Tableau de bord analytique avec statistiques détaillées
- 🔍 Recherche et filtrage avancés
- 📄 Export des statistiques au format Word (.docx)
- 🏠 Page d'accueil personnalisée avec informations légales

### 🆕 Dernières Fonctionnalités
- 📊 Système d'analytics complet avec suivi des visites
- 🖼️ Module de gestion des kakemonos
- 📈 Statistiques avancées avec export Word
- 📧 Système de notification par email amélioré
- 🔒 Sécurité renforcée avec variables d'environnement
- 🎨 Interface utilisateur modernisée avec thème personnalisé

## 📋 Prérequis

- Python 3.9+
- Serveur SMTP pour les emails
- Espace disque pour les médias uploadés
- Base de données SQLite (par défaut) ou PostgreSQL
- Git pour le contrôle de version
- Navigateur web moderne

## 🚀 Installation

1. Cloner le repository
```bash
git clone https://github.com/votre-compte/MediapassReservation.git
cd MediapassReservation
```

2. Créer un environnement virtuel
```bash
python -m venv env
source env/bin/activate  # Linux/Mac
env\Scripts\activate     # Windows
```

3. Installer les dépendances
```bash
pip install -r requirements.txt
```

4. Configurer les variables d'environnement
```bash
# Créer un fichier .env à la racine du projet
# Voir la section Configuration pour les variables nécessaires
```

5. Appliquer les migrations
```bash
python manage.py migrate
```

6. Créer un super utilisateur
```bash
python manage.py createsuperuser
```

7. Collecter les fichiers statiques
```bash
python manage.py collectstatic
```

8. Lancer le serveur
```bash
python manage.py runserver
```

## ⚙️ Configuration

### Configuration Email
Le système utilise SMTP pour l'envoi d'emails. Configurez dans `.env` :
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=votre@email.com
EMAIL_HOST_PASSWORD=votre_mot_de_passe
DEFAULT_FROM_EMAIL=votre@email.com
EMAIL_USE_TLS=True
```

### Configuration de la Base de Données
Par défaut, SQLite est utilisé. Pour PostgreSQL, ajoutez dans `.env` :
```
DATABASE_URL=postgres://user:password@localhost:5432/mediapass
```

### Configuration des Variables d'Environnement
Créez un fichier `.env` à la racine du projet avec :
```
SECRET_KEY=votre_clé_secrète_django
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

## 🏗️ Structure du Projet

```
MediapassReservation/
├── accounts/          # Gestion des utilisateurs et authentification
│   ├── models.py     # Modèles utilisateur personnalisés
│   ├── views.py      # Vues d'authentification
│   └── forms.py      # Formulaires d'authentification
├── shop/             # Gestion des réservations d'équipements
│   ├── models.py     # Modèles pour produits et réservations
│   ├── views.py      # Vues de réservation
│   ├── forms.py      # Formulaires de réservation
│   └── templates/    # Templates pour les équipements
├── workshop/         # Gestion des ateliers
│   ├── models.py     # Modèles pour les ateliers
│   ├── views.py      # Vues des ateliers
│   ├── forms.py      # Formulaires d'ateliers
│   ├── services.py   # Services métier
│   └── utils/        # Utilitaires (export Word)
├── kakemono/         # Gestion des kakemonos
│   ├── models.py     # Modèles pour les kakemonos
│   ├── views.py      # Vues des kakemonos
│   └── forms.py      # Formulaires kakemonos
├── analytics/        # Système d'analytics
│   ├── models.py     # Modèles de suivi
│   ├── views.py      # Vues analytics
│   └── middleware.py # Middleware de suivi
├── home/             # Page d'accueil et informations
│   ├── views.py      # Vues de la page d'accueil
│   └── templates/    # Templates d'accueil
├── app/              # Configuration principale Django
│   ├── settings.py   # Configuration du projet
│   ├── urls.py       # URLs principales
│   └── middleware.py # Middleware global
├── static/           # Fichiers statiques
│   ├── css/          # Styles CSS
│   ├── js/           # Scripts JavaScript
│   ├── img/          # Images et logos
│   └── vendor/       # Bibliothèques tierces
├── templates/        # Templates HTML globaux
├── media/           # Fichiers uploadés par les utilisateurs
├── scripts/         # Scripts utilitaires
└── staticfiles/     # Fichiers statiques collectés
```

## 🔐 Sécurité

- Protection CSRF activée sur tous les formulaires
- Validation des fichiers uploadés (taille et type)
- Variables d'environnement pour les données sensibles
- Authentification requise pour les vues sensibles
- Permissions utilisateur basées sur les rôles
- Middleware de sécurité Django
- Validation des données côté serveur

## 📊 Fonctionnalités Détaillées

### Système de Réservation (Shop)
- Vérification automatique des disponibilités
- Gestion des conflits de réservation
- Système d'approbation des réservations
- Historique des réservations
- Gestion des catégories d'équipements
- Notifications automatiques

### Gestion des Ateliers (Workshop)
- Planification des ateliers
- Gestion des inscriptions
- Statistiques de participation
- Export des données au format Word
- Système de rappels par email
- Gestion des animateurs

### Gestion des Kakemonos
- Réservation d'affiches et banderoles
- Gestion des périodes de disponibilité
- Validation des demandes
- Historique des emprunts

### Analytics et Statistiques
- Suivi des visites utilisateur
- Statistiques d'utilisation
- Export au format Word (.docx)
- Tableau de bord administrateur
- Rapports personnalisables

## 🔧 Technologies Utilisées

- 🐍 Python 3.9+
- 🎯 Django 4.2.2
- 🎨 Bootstrap 5
- 📧 SMTP pour les emails
- 🖼️ Pillow pour la gestion des images
- 🔒 python-decouple pour la configuration
- 📊 python-docx pour l'export Word
- 📅 jQuery pour l'interface utilisateur
- 📈 ApexCharts pour les graphiques
- 🎨 Boxicons pour les icônes
- 📱 Responsive design

## 👥 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add: Amazing Feature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

### Guide de Style
- Utiliser Black pour le formatage Python
- Suivre les conventions PEP 8
- Documenter les nouvelles fonctionnalités
- Ajouter des tests unitaires
- Maintenir la cohérence du code


---

**Développé pour la Communauté de Communes Sud-Avesnois** 🏛️
