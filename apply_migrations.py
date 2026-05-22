#!/usr/bin/env python
"""Script temporaire pour appliquer les migrations Django."""
import os
import django

# Configuration de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    # Appliquer toutes les migrations
    execute_from_command_line(['manage.py', 'migrate'])





