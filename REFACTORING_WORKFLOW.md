# Plan de Refactorisation — MediaPass Reservation System

> **Date :** Mai 2026
> **Objectif :** Garder la BDD et les `models.py`, réécrire tout le frontend (HTML/CSS) + refactoriser le backend Python
> **Framework CSS :** TailwindCSS v4 uniquement (suppression totale de Bootstrap)
> **Ordre :** Du socle global vers chaque app, de la plus simple à la plus complexe

---

## Table des matières

1. [Architecture cible](#1-architecture-cible)
2. [Phase 0 — Fondations globales](#2-phase-0--fondations-globales)
3. [Phase 1 — Base template Tailwind](#3-phase-1--base-template-tailwind)
4. [Phase 2 — Partiels réutilisables](#4-phase-2--partiels-réutilisables)
5. [Phase 3 — Refonte des apps (une par une)](#5-phase-3--refonte-des-apps-une-par-une)
6. [Phase 4 — Nettoyage final](#6-phase-4--nettoyage-final)
7. [Checklist récapitulative](#7-checklist-récapitulative)

---

## 1. Architecture cible

### Avant la refactorisation

```
MediapassReservation/
├── templates/               # 3 bases incompatibles (base.html, base_new.html, base_kakemono.html)
├── static/
│   ├── css/                 # 7 fichiers CSS (Bootstrap + Tailwind mélangés)
│   ├── vendor/              # Bootstrap, jQuery, Sneat theme, etc. (~20 fichiers)
│   └── js/                  # 12 fichiers JS
├── staticfiles/             # Miroir de static/ (collectstatic)
├── accounts/
├── home/
├── shop/                    # 19 templates, views.py de 1526 lignes
├── workshop/                # 19 templates, workshops_stats de 421 lignes
├── library_workshops/       # 12 templates (HTMX) ← meilleur exemple du projet
├── kakemono/                # 8 templates, base isolée
├── distribution/            # 9 templates, print() de debug
├── analytics/               # 1 template
├── notifications/           # 1 template email
└── visitor_tracking/        # 6 templates
```

### Après la refactorisation

```
MediapassReservation/
├── templates/
│   ├── base.html            # UNIQUE base Tailwind-pur
│   ├── email_base.html      # Base emails
│   └── partials/            # Partiels réutilisables
│       ├── _form.html
│       ├── _messages.html
│       └── _pagination.html
├── static/
│   ├── css/
│   │   └── app.css          # UNIQUE fichier CSS (si nécessaire)
│   └── js/
│       └── app.js           # UNIQUE fichier JS (si nécessaire)
├── core/                    # NOUVELLE app
│   ├── permissions.py       # Toutes les fonctions de permissions mutualisées
│   ├── models.py            # TimestampedModel abstrait
│   └── forms.py             # TailwindFormMixin
├── accounts/                # 1 template, views gardées
├── home/                    # 4 templates, views refactorisées
├── shop/                    # 19 templates, views + services refactorisés
├── workshop/                # 19 templates, views refactorisées
├── library_workshops/       # 12 templates, gardé à l'identique (déjà propre)
├── kakemono/                # 8 templates, base supprimée (utilise base.html)
├── distribution/            # 9 templates, views refactorisées
├── analytics/               # 1 template, views gardées
├── notifications/           # 1 template, services étendus
└── visitor_tracking/        # 6 templates, views refactorisées
```

---

## 2. Phase 0 — Fondations globales

### 2.1 Créer l'app `core/`

```bash
python manage.py startapp core
```

Ajouter `"core"` dans `INSTALLED_APPS` de `app/settings.py`.

### 2.2 `core/permissions.py`

**Raison :** Les mêmes fonctions de permissions sont dupliquées dans 3 apps différentes.

```python
from django.contrib.auth.mixins import UserPassesTestMixin
from functools import wraps
from django.shortcuts import redirect


def is_staff_or_superuser(user):
    """Vérifie si l'utilisateur est staff ou superuser."""
    return user.is_staff or user.is_superuser


def is_staff_or_superuser_or_in_comm_group(user):
    """Vérifie si l'utilisateur est staff, superuser ou dans le groupe communication."""
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name="communication").exists()
    )


def group_required(group_name):
    """Décorateur : restreint une vue à un groupe Django spécifique."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if not request.user.groups.filter(name=group_name).exists():
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Accès refusé")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def is_mediatheque_member_or_admin(user):
    """Vérifie si l'utilisateur est membre du groupe mediatheque ou superuser."""
    return user.is_superuser or user.groups.filter(name="mediatheque").exists()


# Mixins pour les class-based views
class StaffMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (request.user.is_staff or request.user.is_superuser):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Accès refusé")
        return super().dispatch(request, *args, **kwargs)
```

### 2.3 `core/models.py`

**Raison :** `created_at` et `updated_at` sont dupliqués dans 8+ modèles.

```python
from django.db import models


class TimestampedModel(models.Model):
    """Ajoute automatiquement created_at et updated_at à un modèle."""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de modification")

    class Meta:
        abstract = True
```

### 2.4 `core/forms.py`

**Raison :** `"class": "form-control"` est répété 50+ fois dans tous les formulaires.

```python
from django import forms


class TailwindFormMixin:
    """
    Applique automatiquement les classes Tailwind aux widgets des formulaires.
    À utiliser en héritage multiple : class MaForm(TailwindFormMixin, forms.ModelForm):
    """
    tailwind_input_class = "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
    tailwind_select_class = "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
    tailwind_textarea_class = "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
    tailwind_checkbox_class = "rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
    tailwind_date_class = "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if hasattr(field, "widget"):
                widget = field.widget
                if isinstance(widget, forms.CheckboxInput):
                    widget.attrs.setdefault("class", self.tailwind_checkbox_class)
                elif isinstance(widget, forms.Select):
                    widget.attrs.setdefault("class", self.tailwind_select_class)
                elif isinstance(widget, forms.Textarea):
                    widget.attrs.setdefault("class", self.tailwind_textarea_class)
                elif isinstance(widget, (forms.DateInput, forms.DateTimeInput, forms.TimeInput)):
                    widget.attrs.setdefault("class", self.tailwind_date_class)
                elif isinstance(widget, (forms.TextInput, forms.EmailInput, forms.NumberInput, forms.URLInput)):
                    widget.attrs.setdefault("class", self.tailwind_input_class)
```

### 2.5 `app/settings.py` — Ajouts

```python
# Ajouter core dans INSTALLED_APPS
INSTALLED_APPS = [
    # ...
    "core",
    # ...
]

# Adresses email (remplacer les hardcodées dans les vues)
CONTACT_EMAIL = "j.brechoire@cc-sudavesnois.fr"
COMM_EMAIL = "c.labroche@cc-sudavesnois.fr"
SIMON_EMAIL = "q.simon@cc-sudavesnois.fr"
```

### 2.6 Ajouter `app_name` dans les URLs

#### `shop/urls.py`
```python
app_name = "shop"

urlpatterns = [
    # ... inchangé
]
```

#### `workshop/urls.py`
```python
app_name = "workshop"

urlpatterns = [
    # ... inchangé
]
```

> **Conséquence :** Tous les `{% url "product_list" %}` dans les templates shop deviendront `{% url "shop:product_list" %}`.
> Même chose pour workshop. À faire dans la réécriture des templates.

---

## 3. Phase 1 — Base template Tailwind

### 3.1 Créer `templates/base.html`

Nouveau base UNIQUE, Tailwind v4 pure, zéro Bootstrap.

```html
{% load static %}
<!DOCTYPE html>
<html lang="fr" class="h-full">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{% block title %}Médi@'pass Réservation{% endblock %}</title>

    <link rel="icon" type="image/x-icon" href="{% static 'img/favicon/favicon.ico' %}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <link rel="stylesheet" href="{% static 'vendor/fonts/boxicons.css' %}" />
    {% block stylesheets %}{% endblock %}
</head>
<body class="h-full bg-gray-50 text-gray-900" style="font-family: Inter, system-ui, sans-serif;">
    <div class="min-h-screen flex">
        <!-- Sidebar (identique à base_new.html, design Tailwind) -->
        <nav class="w-64 bg-white border-r border-gray-200 fixed inset-y-0 left-0 z-40 -translate-x-full lg:translate-x-0 transition-transform duration-200">
            <!-- Logo + navigation -->
            {% include "partials/_sidebar.html" %}
        </nav>

        <!-- Contenu principal -->
        <div class="flex-1 flex flex-col min-w-0 lg:ml-64">
            <!-- Top bar -->
            {% include "partials/_navbar.html" %}

            <main class="flex-1 px-4 sm:px-6 lg:px-8 py-6">
                {% include "partials/_messages.html" %}
                {% include "partials/_pending_alert.html" %}
                {% block content %}{% endblock %}
            </main>

            {% include "partials/_footer.html" %}
        </div>
    </div>

    {% include "partials/_backup_modal.html" %}
    <script src="{% static 'js/app.js' %}"></script>
    {% block javascripts %}{% endblock %}
</body>
</html>
```

### 3.2 Les partiels à créer

#### `templates/partials/_sidebar.html`
Navigation latérale (logo, liens par groupe, catégories).

#### `templates/partials/_navbar.html`
Barre du haut (recherche, profil utilisateur, déconnexion).

#### `templates/partials/_messages.html`
Affichage des messages Django avec Tailwind.

```html
{% if messages %}
<div class="space-y-2 mb-4">
    {% for message in messages %}
    <div class="flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium
        {% if message.tags == 'error' %}bg-red-50 text-red-700 border border-red-200
        {% elif message.tags == 'success' %}bg-green-50 text-green-700 border border-green-200
        {% elif message.tags == 'warning' %}bg-yellow-50 text-yellow-700 border border-yellow-200
        {% else %}bg-blue-50 text-blue-700 border border-blue-200{% endif %}">
        {{ message }}
    </div>
    {% endfor %}
</div>
{% endif %}
```

#### `templates/partials/_pending_alert.html`
Alerte structures en attente de validation.

#### `templates/partials/_footer.html`
Pied de page simple.

#### `templates/partials/_backup_modal.html`
Modal de sauvegarde (superuser uniquement).

#### `templates/partials/_form.html`
Rendu de formulaire standardisé Tailwind.

```html
{% for field in form %}
<div class="mb-4">
    <label for="{{ field.id_for_label }}" class="block text-sm font-medium text-gray-700 mb-1">
        {{ field.label }}
    </label>
    {{ field }}
    {% if field.help_text %}
    <p class="mt-1 text-xs text-gray-500">{{ field.help_text }}</p>
    {% endif %}
    {% for error in field.errors %}
    <p class="mt-1 text-sm text-red-600">{{ error }}</p>
    {% endfor %}
</div>
{% endfor %}
```

#### `templates/partials/_pagination.html`
Pagination Tailwind réutilisable.

### 3.3 `templates/email_base.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8" />
    <style>
        body { font-family: Inter, Arial, sans-serif; color: #333; line-height: 1.6; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { border-bottom: 2px solid #4f46e5; padding-bottom: 10px; margin-bottom: 20px; }
        .footer { border-top: 1px solid #e5e7eb; padding-top: 10px; margin-top: 20px; font-size: 12px; color: #9ca3af; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Médi@'pass Réservation</h2>
        </div>
        {% block email_content %}{% endblock %}
        <div class="footer">
            <p>Cet email a été envoyé automatiquement par le système de réservation Médi@'pass.</p>
        </div>
    </div>
</body>
</html>
```

---

## 4. Phase 2 — Partiels réutilisables

### À créer dans `templates/partials/`

| Fichier | Contenu |
|---|---|
| `_sidebar.html` | Navigation latérale complète (logo, catégories, liens par groupe) |
| `_navbar.html` | Barre supérieure (recherche, menu utilisateur) |
| `_messages.html` | Affichage des messages Django (success/error/warning/info) |
| `_form.html` | Rendu générique de formulaire avec champ + label + erreurs |
| `_pagination.html` | Pagination Tailwind |
| `_modal.html` | Modal générique Tailwind |
| `_backup_modal.html` | Modal de sauvegarde spécifique (superuser) |
| `_pending_alert.html` | Alerte structures en attente |
| `_footer.html` | Pied de page |

### Exemple `_modal.html`

```html
<div id="{{ modal_id }}" class="fixed inset-0 z-50 hidden" role="dialog" aria-modal="true">
    <div class="absolute inset-0 bg-gray-900/60"></div>
    <div class="relative mx-auto mt-24 w-full max-w-lg px-4">
        <div class="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
            <div class="flex items-center justify-between px-5 py-3 border-b border-gray-200">
                <h3 class="text-lg font-semibold">{% block modal_title %}{% endblock %}</h3>
                <button onclick="document.getElementById('{{ modal_id }}').classList.add('hidden')" class="p-2 rounded hover:bg-gray-100">
                    <i class="bx bx-x text-xl"></i>
                </button>
            </div>
            <div class="p-5">
                {% block modal_content %}{% endblock %}
            </div>
        </div>
    </div>
</div>
```

---

## 5. Phase 3 — Refonte des apps (une par une)

### Procédure standard pour chaque app

Pour chaque app, le workflow est le même :

```bash
# 1. Réécrire forms.py avec TailwindFormMixin
# 2. Réécrire views.py (CBV si CRUD, services si logique lourde)
# 3. Réécrire urls.py (ajouter app_name si manquant)
# 4. Supprimer et recréer les templates
# 5. Vérifier
python manage.py check
python manage.py test
```

### 5.1 `accounts` — 1 template

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder (vide) |
| `views.py` | ✅ Garder (login/logout, standard Django) |
| `forms.py` | ✅ Garder (simple, fonctionnel) |
| `urls.py` | ✅ Garder |
| `templates/accounts/login.html` | ❌ Réécrire avec Tailwind |

### 5.2 `home` — 4 templates

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder (vide) |
| `views.py` | ⚠️ Réécrire — remplacer les imports de fonctions dupliquées par `core/permissions.py` |
| `urls.py` | ✅ Garder |
| `templates/home/` | ❌ Réécrire (index, legalinformation, param, search) |

### 5.3 `analytics` — 1 template

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ✅ Garder (simple, délégué à ApexCharts) |
| `templates/analytics/dashboard.html` | ❌ Réécrire avec Tailwind |

### 5.4 `notifications` — 1 template email

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ✅ Garder |
| `services.py` | ⚠️ Étendre — ajouter des fonctions génériques d'envoi d'email utilisables par shop et workshop |
| `templates/notifications/` | ❌ Réécrire avec `email_base.html` |

### 5.5 `visitor_tracking` — 6 templates

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ⚠️ Réécrire avec CBV (`CreateView`, `UpdateView`, `ListView`) |
| `forms.py` | ❌ Réécrire avec `TailwindFormMixin` |
| `templates/visitor_tracking/` | ❌ Réécrire |

### 5.6 `kakemono` — 8 templates

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ⚠️ Réécrire avec CBV pour les CRUD |
| `forms.py` | ❌ Réécrire avec `TailwindFormMixin` |
| `templates/kakemono/` | ❌ Réécrire (héritent du nouveau `base.html`, plus de `base_kakemono.html`) |

> **Important :** `base_kakemono.html` disparaît. Les templates kakemono utilisent `base.html` commun.
> Le `{% block kakemono_content %}` devient `{% block content %}`.

### 5.7 `distribution` — 9 templates

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ⚠️ Réécrire — supprimer les `print()` de debug, passer en CBV |
| `forms.py` | ❌ Réécrire avec `TailwindFormMixin` |
| `templates/distribution/` | ❌ Réécrire |

### 5.8 `library_workshops` — 12 templates

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ✅ Garder (HTMX bien utilisé, code propre) |
| `services.py` | ✅ Garder (modèle à suivre) |
| `templates/library_workshops/` | ❌ Réécrire avec Tailwind |

> C'est l'app la plus propre du projet. On ne touche qu'au HTML (passage en Tailwind).

### 5.9 `workshop` — 19 templates

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder |
| `views.py` | ⚠️ Réécrire — extraire `workshop_stats()` (421 lignes) dans `services.py`, remplacer les `.get()` par `get_object_or_404()` |
| `forms.py` | ❌ Réécrire avec `TailwindFormMixin` |
| `services.py` | ⚠️ Étendre — ajouter les stats |
| `utils/html_to_word.py` | `utils/word_export.py` (renommer pour clarté) |
| `templates/workshop/` | ❌ Réécrire |

### 5.10 `shop` — 19 templates + 2 emails

| Fichier | Action |
|---|---|
| `models.py` | ✅ Garder (⚠️ remplacer `is_approved`/`is_rejected` → `status` dans un second temps) |
| `views.py` (1526 lignes) | ⚠️ Réécrire — extraire dans `services.py`, CBV pour CRUD, email → `notifications/services.py` |
| `forms.py` (292 lignes) | ❌ Réécrire avec `TailwindFormMixin` |
| **Créer** `shop/services.py` | Statistiques, disponibilités, logique d'approbation |
| `templates/shop/` | ❌ Réécrire |
| `templates/shop/mail/` | ❌ Réécrire avec `email_base.html` |

---

## 6. Phase 4 — Nettoyage final

### 6.1 Supprimer les fichiers inutilisés

```bash
# Fichiers CSS obsolètes
Remove-Item -LiteralPath "static/css/demo.css"
Remove-Item -LiteralPath "static/css/style.css"
Remove-Item -LiteralPath "static/css/spectrum.css"
Remove-Item -LiteralPath "static/css/sidebar.css"

# Vendor CSS/JS Bootstrap (le CDN Tailwind remplace tout)
Remove-Item -LiteralPath "static/vendor" -Recurse -Force

# JS superflus (si jQuery, Bootstrap JS, etc. ne sont plus utilisés)
Remove-Item -LiteralPath "static/js/main.js"
Remove-Item -LiteralPath "static/js/sidebar.js"
Remove-Item -LiteralPath "static/js/form-basic-inputs.js"
Remove-Item -LiteralPath "static/js/ui-modals.js"
Remove-Item -LiteralPath "static/js/ui-popover.js"
Remove-Item -LiteralPath "static/js/ui-toasts.js"
Remove-Item -LiteralPath "static/js/config.js"
Remove-Item -LiteralPath "static/js/dashboards-analytics.js"
Remove-Item -LiteralPath "static/js/extended-ui-perfect-scrollbar.js"
Remove-Item -LiteralPath "static/js/pages-account-settings-account.js"

# Anciennes bases templates
Remove-Item -LiteralPath "templates/base_new.html"
Remove-Item -LiteralPath "templates/base_kakemono.html"

# Répertoire staticfiles (à régénérer)
Remove-Item -LiteralPath "staticfiles" -Recurse -Force
```

### 6.2 Commandes finales

```bash
# Vérifier qu'il n'y a pas d'erreurs
python manage.py check --deploy

# Appliquer les migrations (si modèles modifiés)
python manage.py makemigrations
python manage.py migrate

# Régénérer les fichiers statiques
python manage.py collectstatic --noinput

# Lancer les tests
python manage.py test

# Vérification pré-push
python scripts/pre_push_check.py
```

### 6.3 Suppression des `print()` de debug

Rechercher et supprimer :

```bash
# Vérifier qu'il ne reste aucun print() de debug
rg "print\(.*DEBUG" --include="*.py"
```

### 6.4 Remplacer les `.get()` non protégés

Rechercher les `model.objects.get(pk=` sans `get_object_or_404` :

```bash
rg "\.objects\.get\(pk=" --include="*.py"
```

---

## 7. Checklist récapitulative

### Phase 0 — Fondations
- [ ] `python manage.py startapp core`
- [ ] Créer `core/permissions.py` (mutualiser toutes les permissions)
- [ ] Créer `core/models.py` (TimestampedModel abstrait)
- [ ] Créer `core/forms.py` (TailwindFormMixin)
- [ ] Ajouter `"core"` dans `INSTALLED_APPS`
- [ ] Ajouter les emails dans `settings.py`
- [ ] Ajouter `app_name` dans `shop/urls.py`
- [ ] Ajouter `app_name` dans `workshop/urls.py`

### Phase 1 — Base template
- [ ] Créer `templates/base.html` (Tailwind pur)
- [ ] Créer `templates/email_base.html`
- [ ] Créer `templates/partials/_sidebar.html`
- [ ] Créer `templates/partials/_navbar.html`
- [ ] Créer `templates/partials/_messages.html`
- [ ] Créer `templates/partials/_form.html`
- [ ] Créer `templates/partials/_pagination.html`
- [ ] Créer `templates/partials/_modal.html`
- [ ] Créer `templates/partials/_backup_modal.html`
- [ ] Créer `templates/partials/_pending_alert.html`
- [ ] Créer `templates/partials/_footer.html`

### Phase 2 — Apps (dans l'ordre)
- [ ] `accounts/login.html`
- [ ] `home/` (4 templates)
- [ ] `analytics/` (1 template)
- [ ] `notifications/` (1 template)
- [ ] `visitor_tracking/` (6 templates + forms + views)
- [ ] `kakemono/` (8 templates + forms + views)
- [ ] `distribution/` (9 templates + forms + views)
- [ ] `library_workshops/` (12 templates)
- [ ] `workshop/` (19 templates + forms + views)
- [ ] `shop/` (19 templates + forms + views + services)

### Phase 3 — Nettoyage
- [ ] Supprimer `static/css/demo.css`
- [ ] Supprimer `static/css/style.css`
- [ ] Supprimer `static/css/spectrum.css`
- [ ] Supprimer `static/css/sidebar.css`
- [ ] Supprimer `static/vendor/`
- [ ] Supprimer les JS inutilisés
- [ ] Supprimer `templates/base_new.html`
- [ ] Supprimer `templates/base_kakemono.html`
- [ ] Supprimer `staticfiles/` puis `collectstatic`
- [ ] Supprimer les `print()` de debug
- [ ] Remplacer les `.get()` par `get_object_or_404()`

### Final
- [ ] `python manage.py check --deploy`
- [ ] `python manage.py test`
- [ ] `python manage.py collectstatic --noinput`
- [ ] `python scripts/pre_push_check.py`

---

## Annexe : Commandes utiles

### Rechercher les doublons de fonctions

```bash
# Chercher les fonctions de permissions dupliquées
rg "def is_staff_or_superuser" --include="*.py"

# Chercher les print() de debug
rg "print\(.*[Dd][Ee][Bb][Uu][Gg]" --include="*.py"

# Chercher les .get() non protégés
rg "\.objects\.get\(pk=" --include="*.py"

# Chercher les adresses email hardcodées
rg "@cc-sudavesnois" --include="*.py"
```

### Compter les templates par app avant/après

```bash
# Avant
Get-ChildItem -Recurse -Filter "*.html" -Path "templates", "*/templates" | Group-Object Directory | Select-Object Count, Name

# Statique
Get-ChildItem -Recurse -Filter "*.css" -Path "static/css" | Measure-Object
Get-ChildItem -Recurse -Filter "*.js" -Path "static" | Measure-Object
Get-ChildItem -Recurse -Filter "*" -Path "static/vendor" | Measure-Object
```
