# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MediaPass Reservation System - A Django web application for managing multimedia equipment reservations, workshops, and promotional materials (kakemonos) for the Communauté de Communes Sud-Avesnois. The UI is in French.

## Common Commands

```bash
# Development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files (for deployment)
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Run tests
python manage.py test

# Send reservation reminders (cron job)
python manage.py send_reservation_reminders

# Generate demo data (69 workshops + participants, user "anor")
python manage.py generate_seed_data

# Pre-push checks (runs tests, migrations check, Black, flake8, isort)
python scripts/pre_push_check.py
```

## Architecture

**Django Apps (each self-contained with models, views, urls, templates, forms):**
- `shop/` - Equipment reservations with approval workflow, conflict detection, availability checking
- `workshop/` - Workshop management with attendance tracking, Word export via `services.py`
- `library_workshops/` - Library-specific workshops with participant management (HTMX-based), requires "mediatheque" group
- `kakemono/` - Promotional materials (posters/banners) reservations
- `distribution/` - Distribution campaigns management
- `analytics/` - Page visit tracking via `AnalyticsMiddleware`
- `notifications/` - Email notifications, J-1 reminders for reservations
- `accounts/` - User authentication
- `home/` - Homepage and static content

**Configuration:**
- `app/settings.py` - Main Django config
- `.env` - Environment variables (SECRET_KEY, EMAIL_*, DATABASE_URL)
- Admin URL: `/mediapassadmin/`

**Key Patterns:**
- Class-based views for complex logic, function-based views for HTMX endpoints
- Business logic in models or `services.py` files
- HTMX for dynamic UI without page reloads
- Bootstrap 5 for frontend styling
- Django ORM exclusively (no raw SQL)

## Code Style

- PEP 8, use Black for formatting
- snake_case for variables/functions, PascalCase for classes
- Use `reverse()` or `{% url %}` for links
- Use `get_object_or_404()` over manual `.get()`
- Use Django's `messages` framework for user feedback
- Use logging instead of `print()`

## When Creating New Apps

1. Create `urls.py` with `urlpatterns` list
2. Create `templates/app_name/` directory
3. Register in `settings.py` under `INSTALLED_APPS`
4. Include in `app/urls.py`: `path("app_name/", include("app_name.urls"))`
