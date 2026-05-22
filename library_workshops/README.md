# Application Library Workshops

Cette application Django gère les ateliers de la médiathèque avec un système complet de gestion des participants.

## Fonctionnalités

### Gestion des ateliers
- **Création d'ateliers** : Formulaire complet avec validation des dates, horaires et tranches d'âge
- **Modification d'ateliers** : Édition des informations existantes
- **Suppression d'ateliers** : Confirmation avant suppression
- **Affichage des ateliers** : Vue d'ensemble avec statistiques

### Gestion des participants
- **Ajout de participants** : Formulaire unifié avec basculement individuel/groupe
- **Réservations de groupe** : Une personne peut réserver pour plusieurs personnes (2-10 personnes)
- **Gestion des listes** : Participants confirmés et liste d'attente
- **Actions rapides** : Déplacer entre les listes, supprimer des participants
- **Validation d'âge** : Respect des tranches d'âge définies pour l'atelier

### Interface utilisateur
- **Design moderne** : Interface Bootstrap avec icônes Boxicons
- **Interactions HTMX** : Actions dynamiques sans rechargement de page
- **Responsive** : Compatible mobile et desktop
- **Accessibilité** : Tooltips, confirmations et messages d'état

## Modèles de données

### Workshop
- Informations de base (titre, description, lieu)
- Dates et horaires (début/fin, support multi-jours)
- Capacité et tranches d'âge
- Métadonnées (créateur, dates de création/modification)

### WorkshopParticipant
- Informations personnelles (nom, prénom, âge)
- Contact (email, téléphone optionnels)
- Statut (confirmé, liste d'attente, annulé)
- Gestion des groupes (responsable, membres, taille du groupe)
- Notes et historique

## URLs principales

- `/library_workshops/` - Liste des ateliers
- `/library_workshops/create/` - Créer un atelier
- `/library_workshops/edit/<id>/` - Modifier un atelier
- `/library_workshops/workshop/<id>/participants/` - Gérer les participants
- `/library_workshops/workshop/<id>/add-participant/` - Ajouter un participant
- `/library_workshops/workshop/<id>/add-group-reservation/` - Réservation de groupe

## Permissions

L'application nécessite que l'utilisateur soit :
- Connecté (`@login_required`)
- Membre du groupe "mediatheque" ou super utilisateur

## Fonctionnalités avancées

### Gestion automatique des listes
- Ajout automatique en liste d'attente si l'atelier est complet
- Validation de l'âge selon les critères de l'atelier
- Messages informatifs pour guider l'utilisateur

### Réservations de groupe
- Création automatique de plusieurs participants en une seule fois
- Gestion du responsable du groupe avec informations complètes
- Membres du groupe créés automatiquement avec références
- Limitation de 2 à 10 personnes par groupe
- Aperçu en temps réel du nombre de participants créés
- Basculement facile entre mode individuel et groupe dans le même formulaire

### Interactions HTMX
- Ajout de participants sans rechargement
- Déplacement entre listes en temps réel
- Suppression avec confirmation
- Messages de succès/erreur dynamiques

### Statistiques en temps réel
- Nombre de participants confirmés
- Taille de la liste d'attente
- Places disponibles
- Capacité totale

## Installation et configuration

1. Assurez-vous que l'application est dans `INSTALLED_APPS`
2. Exécutez les migrations : `python manage.py migrate library_workshops`
3. Créez un groupe "mediatheque" si nécessaire
4. Ajoutez les URLs dans le fichier principal `urls.py`

## Utilisation

### Pour les administrateurs
1. Accédez à la liste des ateliers
2. Créez un nouvel atelier avec les informations requises
3. Gérez les participants via les boutons d'action
4. Surveillez les statistiques en temps réel

### Pour les utilisateurs
1. Consultez la liste des ateliers disponibles
2. Ajoutez des participants selon les disponibilités (individuel ou groupe)
3. Basculez facilement entre mode individuel et groupe
4. Gérez les listes d'attente si nécessaire
5. Consultez les notes et informations des participants

## Personnalisation

### Styles
L'application utilise Bootstrap 5 et Boxicons. Les styles peuvent être personnalisés via :
- Variables CSS Bootstrap
- Classes utilitaires Tailwind (si configuré)
- Styles personnalisés dans `static/css/`

### Validation
Les validations peuvent être étendues dans :
- `forms.py` - Validation des formulaires
- `models.py` - Validation des modèles
- `views.py` - Logique métier personnalisée

## Support

Pour toute question ou problème, consultez :
- La documentation Django officielle
- Les logs de l'application
- Les messages d'erreur dans l'interface utilisateur 