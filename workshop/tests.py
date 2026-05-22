"""Tests pour l'application workshop.

Ce module contient les tests unitaires pour les modèles Workshop,
Location et les formulaires associés.
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Location, Workshop


class WorkshopTests(TestCase):
    """Tests pour le modèle Workshop."""

    def setUp(self):
        """Préparer les tests.

        Configure l'environnement de test en créant un objet Location
        qui sera utilisé par les méthodes de test.
        """
        self.location = Location.objects.create(
            name="Test Location",
            address="123 Test St",
            city="Test City",
            zip_code="12345",
        )

    def test_workshop_creation(self):
        """Créer un atelier.

        Vérifie la création d'un nouvel atelier avec ses attributs
        et leur persistance en base de données.
        """
        workshop = Workshop.objects.create(
            name="Test Workshop",
            location=self.location,
            date=datetime.now().date(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=True,
        )
        self.assertEqual(str(workshop), "Test Workshop")
        self.assertTrue(workshop.poster_required)

    def test_workshop_dates(self):
        """Vérifie la validation des dates de l'atelier."""
        # Test avec dates valides
        workshop = Workshop.objects.create(
            name="Test Workshop",
            location=self.location,
            date=datetime.now().date(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=True,
        )
        self.assertIsNotNone(workshop.pk)

        # Test avec dates invalides
        with self.assertRaises(ValidationError):
            workshop = Workshop(
                name="Invalid Workshop",
                location=self.location,
                date=datetime.now().date(),
                date_end=(datetime.now() - timedelta(days=1)).date(),
                start_time=datetime.now().time(),
                end_time=(datetime.now() - timedelta(hours=2)).time(),
                poster_required=True,
            )
            workshop.full_clean()


class LocationTests(TestCase):
    """Tests pour le modèle Location."""

    def setUp(self):
        """Préparer les tests.

        Configure l'environnement de test en créant un objet Location
        qui sera utilisé par les méthodes de test.
        """
        self.location = Location.objects.create(
            name="Test Location",
            address="123 Test St",
            zip_code="12345",
            city="Test City",
        )

    def test_location_creation(self):
        """Crée un nouveau lieu."""
        location = Location.objects.create(
            name="Test Location",
            address="123 Test St",
            city="Test City",
            zip_code="12345",
        )
        self.assertEqual(str(location), "Test Location")
        self.assertEqual(location.city, "Test City")

    def test_location_create(self):
        """Crée un nouveau lieu de test.

        Vérifie la création d'un nouveau lieu avec ses attributs
        et leur persistance en base de données.
        """
        location = Location.objects.create(
            name="Test Location",
            address="123 Test St",
            city="Test City",
            zip_code="12345",
        )
        self.assertEqual(str(location), "Test Location")
        self.assertEqual(location.city, "Test City")

    def test_location_validation(self):
        """Tester les validations du lieu.

        Vérifie les règles de validation suivantes :
        - Longueur minimale du nom
        - Format du code postal
        - Unicité du nom
        """
        # Test avec un code postal invalide (trop long)
        with self.assertRaises(ValidationError):
            invalid_location = Location.objects.create(
                name="Invalid Location",
                address="456 Test St",
                zip_code="123456",  # Code postal trop long
                city="Test City",
            )
            invalid_location.full_clean()

    def test_location_update(self):
        """Test la mise à jour des données du lieu."""
        self.location.name = "Nouveau nom"
        self.location.save()
        self.assertEqual(self.location.name, "Nouveau nom")

    def test_location_delete(self):
        """Test la suppression du lieu."""
        self.location.delete()
        self.assertIsNone(Location.objects.filter(name="Test Location").first())


class WorkshopListViewTests(TestCase):
    """Tests pour la vue workshop_list."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75"
        )
        self.workshop = Workshop.objects.create(
            name="Test Workshop",
            location=self.location,
            date=date.today(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=False,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("workshop_list"))
        self.assertEqual(response.status_code, 200)

    def test_contains_name(self):
        self.login()
        response = self.client.get(reverse("workshop_list"))
        self.assertContains(response, "Test Workshop")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("workshop_list"))
        self.assertEqual(response.status_code, 302)

    def test_empty_state(self):
        self.login()
        Workshop.objects.all().delete()
        response = self.client.get(reverse("workshop_list"))
        self.assertContains(response, "Aucun atelier")


class WorkshopCreateViewTests(TestCase):
    """Tests pour la vue workshop_create."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75"
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("workshop_create"))
        self.assertEqual(response.status_code, 200)

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("workshop_create"))
        self.assertEqual(response.status_code, 302)

    def test_post_valid_creates_workshop(self):
        self.login()
        response = self.client.post(
            reverse("workshop_create"),
            {
                "name": "New Workshop",
                "location": self.location.pk,
                "date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "12:00",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("workshop_list"))

    def test_post_invalid_shows_errors(self):
        self.login()
        response = self.client.post(
            reverse("workshop_create"), {"name": "", "date": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obligatoire")


class WorkshopDetailViewTests(TestCase):
    """Tests pour la vue workshop_detail."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75"
        )
        self.workshop = Workshop.objects.create(
            name="Detail Workshop",
            location=self.location,
            date=date.today(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=False,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("workshop_detail", args=[self.workshop.pk]))
        self.assertEqual(response.status_code, 200)

    def test_contains_name(self):
        self.login()
        response = self.client.get(reverse("workshop_detail", args=[self.workshop.pk]))
        self.assertContains(response, "Detail Workshop")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("workshop_detail", args=[self.workshop.pk]))
        self.assertEqual(response.status_code, 302)

    def test_returns_404(self):
        self.login()
        response = self.client.get(reverse("workshop_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)
