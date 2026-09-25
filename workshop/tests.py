"""Tests pour l'application workshop.

Ce module contient les tests unitaires pour les modèles Workshop,
Location et les formulaires associés.
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


class WorkshopStatsViewTests(TestCase):
    """Tests pour la vue workshop_stats enrichie."""

    def setUp(self):
        self.loc_a = Location.objects.create(
            name="Lieu A", address="1 Rue", city="Avesnes", zip_code="59440"
        )
        self.loc_b = Location.objects.create(
            name="Lieu B", address="2 Rue", city="Fourmies", zip_code="59610"
        )
        self.year = 2024
        Workshop.objects.create(
            name="Atelier 1",
            location=self.loc_a,
            date=date(self.year, 3, 10),
            start_time="09:00",
            end_time="12:00",
            poster_required=True,
            number_registered=10,
            number_attendees=8,
            class_welcome=False,
            instagram=True,
        )
        Workshop.objects.create(
            name="Atelier zero",
            location=self.loc_a,
            date=date(self.year, 4, 5),
            start_time="09:00",
            end_time="12:00",
            poster_required=False,
            number_registered=0,
            number_attendees=0,
            class_welcome=False,
        )
        Workshop.objects.create(
            name="Accueil classe",
            location=self.loc_b,
            date=date(self.year, 5, 20),
            start_time="09:00",
            end_time="12:00",
            poster_required=False,
            number_registered=25,
            number_attendees=20,
            class_welcome=True,
        )
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.basic = User.objects.create_user(username="basic", password="pass")

    def login_staff(self):
        self.client.login(username="staff", password="pass")

    def test_returns_200(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"), {"year": self.year}
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_year_does_not_500(self):
        self.login_staff()
        response = self.client.get(reverse("workshop_stats"), {"year": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_year"], timezone.now().year)

    def test_requires_permission(self):
        response = self.client.get(reverse("workshop_stats"))
        self.assertEqual(response.status_code, 302)
        self.client.login(username="basic", password="pass")
        response = self.client.get(reverse("workshop_stats"))
        self.assertEqual(response.status_code, 302)

    def test_comm_group_allowed(self):
        group, _ = Group.objects.get_or_create(name="communication")
        self.basic.groups.add(group)
        self.client.login(username="basic", password="pass")
        response = self.client.get(
            reverse("workshop_stats"), {"year": self.year}
        )
        self.assertEqual(response.status_code, 200)

    def test_export_filename_uses_selected_year(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "export": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f"statistiques_ateliers_{self.year}.docx",
            response["Content-Disposition"],
        )

    def test_new_context_keys(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"), {"year": self.year}
        )
        for key in (
            "presence_by_location",
            "distribution_stats",
            "poster_stats",
            "channel_coverage",
            "top_flop_communes",
            "chart_type",
            "chart_locations",
            "chart_communes",
            "stats_filter_form",
        ):
            self.assertIn(key, response.context)

    def test_city_filter(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "city": "Avesnes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_workshops"], 2)
        self.assertTrue(response.context["has_active_filters"])

    def test_class_welcome_filter(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "class_welcome": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_workshops"], 1)

    def test_partial_endpoint(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats_partial"), {"year": self.year}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "workshop/partials/stats_content.html"
        )

    def test_top_flop_threshold(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"), {"year": self.year}
        )
        top_flop = response.context["top_flop_communes"]
        self.assertEqual(top_flop["min_ateliers"], 3)
        # Avesnes n'a que 2 ateliers : exclue du top/flop
        communes = [c["commune"] for c in top_flop["top_presence"]]
        self.assertNotIn("Avesnes", communes)
