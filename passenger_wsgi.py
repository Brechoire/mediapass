"""Configuration WSGI pour le déploiement avec Passenger.

Ce module configure l'application WSGI pour le déploiement avec Passenger,
en ajoutant le répertoire du projet au chemin Python et en important
l'application WSGI depuis le module wsgi.py.
"""

import imp
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

wsgi = imp.load_source("wsgi", "app/wsgi.py")
application = wsgi.application
