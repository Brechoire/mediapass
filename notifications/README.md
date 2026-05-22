# Application Notifications

Cette application gère les notifications par email, notamment les rappels de réservation.

## Fonctionnalités

- **Rappels de réservation J-1** : Envoi automatique d'emails de rappel pour les réservations se terminant le lendemain
- **Gestion dynamique des destinataires** : Ajout/modification/suppression des adresses email via l'interface d'administration Django
- **Historique des rappels** : Suivi de tous les rappels envoyés

## Configuration

### 1. Migrations

```bash
python manage.py migrate
```

### 2. Configuration des destinataires

1. Accédez à l'interface d'administration Django
2. Allez dans la section "Notifications" > "Destinataires de notifications"
3. Ajoutez les adresses email qui doivent recevoir les rappels
4. Assurez-vous que le champ "Actif" est coché

### 3. Activation des rappels

Les rappels sont **activés par défaut**. Vous pouvez activer ou désactiver le système via l'interface d'administration Django (section "Notifications" > "Paramètres de notification").

### 4. Configuration de l'heure d'envoi

L'heure d'envoi des rappels est configurable via l'interface d'administration Django (section "Notifications" > "Paramètres de notification").

### 5. Configuration du cron

Pour que les rappels soient envoyés automatiquement chaque jour, configurez une tâche cron sur votre hébergeur :

```bash
# Exemple générique (adaptez les chemins)
cd /chemin/vers/le/projet && /chemin/vers/python manage.py send_reservation_reminders
```

**Planification :**
- Exécution quotidienne à l'heure configurée dans Django
- Exemple : `0 9 * * *` pour 9h00

### Test manuel

```bash
python manage.py send_reservation_reminders
```

## Utilisation

La commande `send_reservation_reminders` :
- Récupère toutes les réservations approuvées qui se terminent demain
- Vérifie qu'aucun rappel n'a déjà été envoyé
- Envoie un email à tous les destinataires actifs
- Marque les réservations comme ayant reçu un rappel
- Crée un historique dans la base de données

## Structure

- `models.py` : Modèles `EmailTemplate`, `NotificationRecipient`, `ReservationReminder`, `WorkshopReminder` et `NotificationSettings`
- `services.py` : Service d'envoi d'emails
- `email_service.py` : Service centralisé d'envoi de notifications
- `admin.py` : Configuration de l'interface d'administration
- `management/commands/` : Commandes pour envoyer les rappels

## Notes importantes

- Les rappels sont envoyés uniquement pour les réservations **approuvées**
- Un rappel n'est envoyé qu'**une seule fois** par réservation
- Les destinataires doivent être **actifs** pour recevoir les emails
- L'heure du cron doit correspondre à l'heure configurée dans Django
