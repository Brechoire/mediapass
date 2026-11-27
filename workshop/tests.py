"""Tests pour l'application workshop.

Ce module contient les tests unitaires pour les modèles Workshop,
Location et les formulaires associés.
"""

from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from docx import Document
from PIL import Image

from app.validators import validate_image_size
from .charts import render_animations_chart, render_monthly_chart
from .forms import WorkshopForm, WorkshopPosterForm
from .images import optimize_workshop_image
from .models import Location, Workshop, WorkshopName
from .naming import (
    build_catalog_plan,
    clean_display_name,
    normalize_workshop_name,
    resolve_workshop_name,
)
from .recurrence import (
    RECURRENCE_BIWEEKLY,
    RECURRENCE_MONTHLY,
    RECURRENCE_NONE,
    RECURRENCE_WEEKLY,
    occurrence_dates,
)
from .reporting import build_animation_report, canonical_animation_key


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

    def test_delete_requires_post(self):
        """La suppression exige POST : le lien GET historique répond 405."""
        self.login()
        response = self.client.get(
            reverse("workshop_delete", args=[self.workshop.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            Workshop.objects.filter(pk=self.workshop.pk).exists()
        )

    def test_delete_post_removes_workshop(self):
        self.login()
        response = self.client.post(
            reverse("workshop_delete", args=[self.workshop.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Workshop.objects.filter(pk=self.workshop.pk).exists()
        )

    def test_delete_button_is_post_form_with_csrf(self):
        from django.urls import reverse as url_reverse

        self.login()
        response = self.client.get(reverse("workshop_list"))
        delete_url = url_reverse(
            "workshop_delete", args=[self.workshop.pk]
        )
        self.assertContains(response, f'action="{delete_url}"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertNotContains(response, "onclick=\"return confirm")

    def test_comm_group_hides_admin_actions(self):
        from django.contrib.auth.models import Group
        from django.urls import reverse as url_reverse

        group, _ = Group.objects.get_or_create(name="communication")
        basic = User.objects.create_user(username="comm", password="pass")
        basic.groups.add(group)
        self.client.login(username="comm", password="pass")
        response = self.client.get(reverse("workshop_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Ajouter un atelier")
        self.assertNotContains(
            response, url_reverse("workshop_create")
        )
        self.assertNotContains(
            response, url_reverse("workshop_update", args=[self.workshop.pk])
        )
        self.assertNotContains(
            response, url_reverse("workshop_delete", args=[self.workshop.pk])
        )
        # La consultation reste possible.
        self.assertContains(response, "Test Workshop")

    def test_chips_show_location_name_and_hide_sort(self):
        self.login()
        response = self.client.get(
            reverse("workshop_list"),
            {"location": self.location.pk, "sort": "-date"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Loc", content)
        self.assertNotIn("Lieu #", content)
        self.assertNotIn("sort:", content)

    def test_year_switch_preserves_filters(self):
        self.login()
        response = self.client.get(
            reverse("workshop_list"), {"location": self.location.pk}
        )
        self.assertEqual(response.status_code, 200)
        # Les pastilles d'années conservent le filtre lieu.
        # (le & littéral du template n'est pas échappé, comme le reste de la page)
        self.assertContains(
            response,
            f"?year={date.today().year}&location={self.location.pk}",
        )

    def test_table_accessibility_and_native_details(self):
        self.login()
        response = self.client.get(reverse("workshop_list"))
        content = response.content.decode()
        self.assertIn("<details", content)
        self.assertNotIn('id="filterPanel"', content)
        self.assertIn("<caption", content)
        self.assertIn('scope="col"', content)
        self.assertIn('aria-sort="descending"', content)
        self.assertIn(
            'class="w-full bg-white border border-[#dce3ef] rounded-lg',
            content,
        )


class LocationDetailViewTests(TestCase):
    """Tests pour la vue location_detail (régression : FieldError 500
    quand l'alias d'agrégat masquait le champ class_welcome)."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75"
        )
        Workshop.objects.create(
            name="Atelier classique",
            location=self.location,
            date=date.today(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=False,
            number_registered=10,
            number_attendees=8,
            class_welcome=False,
        )
        Workshop.objects.create(
            name="Accueil classe",
            location=self.location,
            date=date.today(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=False,
            number_registered=25,
            number_attendees=20,
            class_welcome=True,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(
            reverse("location_detail", args=[self.location.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_aggregate_counts(self):
        self.login()
        response = self.client.get(
            reverse("location_detail", args=[self.location.pk])
        )
        self.assertEqual(response.context["total_workshops"], 2)
        self.assertEqual(response.context["classic_count"], 1)
        self.assertEqual(response.context["class_welcome_count"], 1)
        self.assertEqual(response.context["total_registered"], 35)
        self.assertEqual(response.context["total_attendees"], 28)

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(
            reverse("location_detail", args=[self.location.pk])
        )
        self.assertEqual(response.status_code, 302)


class WorkshopPosterViewsTests(TestCase):
    """Les observations de l'atelier sont visibles côté affiches."""

    LONG_OBS = (
        "Prévoir des feutres effaçables et du papier A3 en quantité suffisante "
        "pour tous les participants inscrits, ainsi qu'une nappe de protection "
        "pour les tables de la salle polyvalente et de quoi nettoyer après."
    )

    def setUp(self):
        from django.contrib.auth.models import Group

        group, _ = Group.objects.get_or_create(name="communication")
        self.user = User.objects.create_user(username="comm", password="pass")
        self.user.groups.add(group)
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75"
        )
        self.with_obs = Workshop.objects.create(
            name="Atelier Obs",
            location=self.location,
            date=date.today(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=True,
            observations=self.LONG_OBS,
        )
        self.without_obs = Workshop.objects.create(
            name="Atelier Sans Obs",
            location=self.location,
            date=date.today(),
            start_time=datetime.now().time(),
            end_time=(datetime.now() + timedelta(hours=2)).time(),
            poster_required=True,
            observations="",
        )

    def login(self):
        self.client.login(username="comm", password="pass")

    def test_demandes_shows_truncated_observations(self):
        self.login()
        response = self.client.get(reverse("workshops_with_poster"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Début du texte présent, fin coupée à ~120 caractères.
        self.assertIn("Prévoir des feutres", content)
        self.assertNotIn("nettoyer après.", content)
        self.assertIn("Voir la suite", content)

    def test_demandes_shows_block_only_when_present(self):
        self.login()
        response = self.client.get(reverse("workshops_with_poster"))
        # Un seul encadré : l'atelier sans observations n'en a pas.
        self.assertContains(response, "Observations :", count=1)

    def test_valide_poster_shows_full_observations(self):
        self.login()
        response = self.client.get(
            reverse("workshop_valide_poster", args=[self.with_obs.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Observations de la demande")
        # Texte intégral, pas de troncature ici.
        self.assertContains(response, "nettoyer après.")

    def test_valide_poster_hides_block_when_empty(self):
        self.login()
        response = self.client.get(
            reverse("workshop_valide_poster", args=[self.without_obs.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Observations de la demande")

    def test_requires_communication_group(self):
        User.objects.create_user(username="basic", password="pass")
        self.client.login(username="basic", password="pass")
        response = self.client.get(reverse("workshops_with_poster"))
        self.assertNotEqual(response.status_code, 200)


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

    def test_post_invalid_preserves_selected_location(self):
        self.login()
        response = self.client.post(
            reverse("workshop_create"),
            {"name": "", "location": self.location.pk, "date": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{self.location.pk}" selected>Loc — Paris</option>',
            html=True,
        )


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

    def test_weekday_filter(self):
        self.login_staff()
        # 2024-05-20 = lundi -> week_day Django = 2
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "weekday": "2"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_workshops"], 1)
        self.assertTrue(response.context["has_active_filters"])

    def test_invalid_weekday_does_not_500(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "weekday": "abc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_workshops"], 3)

    def test_slot_filter(self):
        self.login_staff()
        # Les 3 ateliers de test sont à 09:00 -> matin.
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "slot": "matin"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_workshops"], 3)
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "slot": "soir"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_workshops"], 0)

    def test_new_abc_context_keys(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"), {"year": self.year}
        )
        for key in (
            "fill_tranches",
            "noshow_top",
            "zero_registered",
            "pareto",
            "recurrence",
            "weekday_stats",
            "slot_stats",
            "duration_stats",
            "coverage_gaps",
            "location_load",
            "active_weekday",
            "active_slot",
            "synthese",
        ):
            self.assertIn(key, response.context)
        self.assertEqual(len(response.context["weekday_stats"]), 7)
        self.assertEqual(len(response.context["slot_stats"]), 3)

    def test_synthese_content(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_stats"), {"year": self.year}
        )
        synthese = response.context["synthese"]
        phrases = synthese["phrases"]
        # ~10 lignes, ton naturel, déterministe.
        self.assertGreaterEqual(len(phrases), 8)
        self.assertLessEqual(len(phrases), 12)
        full = " ".join(phrases)
        self.assertIn(str(self.year), full)
        self.assertIn("3 ateliers", full)
        # Export Word reprend la synthèse sans 500.
        response = self.client.get(
            reverse("workshop_stats"),
            {"year": self.year, "export": "1"},
        )
        self.assertEqual(response.status_code, 200)


class AnimationGroupingTests(SimpleTestCase):
    """Tests du regroupement des intitulés d'animations."""

    def test_canva_variants_share_key(self):
        variants = [
            "Découverte Canva",
            "Initiation Canva",
            "Découvrir et apprendre Canva",
            "Découvrez Canva en pratique - Créez comme un pro !",
        ]
        self.assertEqual(
            {canonical_animation_key(variant) for variant in variants},
            {"canva"},
        )

    def test_case_accents_and_plurals_are_normalized(self):
        variants = [
            "Atelier Jeux vidéo",
            "Atelier jeux video",
            "Jeux vidéo",
        ]
        self.assertEqual(
            {canonical_animation_key(variant) for variant in variants},
            {"jeux video"},
        )
        self.assertEqual(
            canonical_animation_key("Atelier Robots"),
            canonical_animation_key("Atelier Robot"),
        )

    def test_program_parenthetical_is_ignored(self):
        self.assertEqual(
            canonical_animation_key(
                "Atelier Jeux vidéo (Minecraft, FC 27, Just Dance...)"
            ),
            "jeux video",
        )
        self.assertNotEqual(
            canonical_animation_key(
                "Atelier Jeux vidéo (Minecraft, FC 27, Just Dance...)"
            ),
            canonical_animation_key("Just Dance"),
        )

    def test_theme_parenthetical_is_kept(self):
        self.assertEqual(
            canonical_animation_key("Dessins sur tablette (Spécial noël)"),
            canonical_animation_key("Dessin sur tablette spécial Noël"),
        )

    def test_distinct_topics_are_not_merged(self):
        keys = {
            canonical_animation_key("Musique sur tablette"),
            canonical_animation_key("Dessins sur tablette"),
            canonical_animation_key("Programmation sur tablette"),
        }
        self.assertEqual(len(keys), 3)
        self.assertNotEqual(
            canonical_animation_key("Atelier informatique"),
            canonical_animation_key("Programmation Informatique"),
        )
        self.assertNotEqual(
            canonical_animation_key("Dessins de Pâques sur tablette"),
            canonical_animation_key(
                "Dessins sur tablette spécial halloween !"
            ),
        )
        self.assertNotEqual(
            canonical_animation_key("Tournoi FIFA"),
            canonical_animation_key("Tournoi Mario Kart"),
        )

    def test_robot_and_ia_aliases(self):
        robot_variants = [
            "Atelier Robot",
            "Atelier Robots",
            "Atelier construction robot",
            "Construis et programme ton robot !",
        ]
        self.assertEqual(
            {canonical_animation_key(variant) for variant in robot_variants},
            {"robot"},
        )
        ia_variants = [
            "Café IA",
            "Café débat sur l'IA",
            "Atelier IA",
            "Découvre l'Intelligence Artificielle en t'amusant",
        ]
        self.assertEqual(
            {canonical_animation_key(variant) for variant in ia_variants},
            {"ia"},
        )
        self.assertEqual(
            canonical_animation_key("Portrait autour de l'IA"),
            "portrait ia",
        )

    def test_inter_centre_is_a_format(self):
        self.assertEqual(
            canonical_animation_key("Inter centre jeux vidéo"),
            "jeux video",
        )
        self.assertEqual(
            canonical_animation_key(
                "Atelier InterCentre Tournoi Mario Kart"
            ),
            "mario kart",
        )

    def test_empty_title_has_fallback(self):
        self.assertEqual(canonical_animation_key(""), "sans intitule")
        self.assertEqual(canonical_animation_key("Atelier"), "sans intitule")


class AnimationReportAggregationTests(TestCase):
    """Tests des agrégats du rapport par animation et par commune."""

    def setUp(self):
        self.year = 2024
        self.loc_a = Location.objects.create(
            name="Lieu A", address="1 Rue", city="Avesnes", zip_code="59440"
        )
        self.loc_b = Location.objects.create(
            name="Lieu B", address="2 Rue", city="Fourmies", zip_code="59610"
        )
        self.loc_unknown = Location.objects.create(
            name="Lieu sans ville", address="3 Rue", city="", zip_code="59000"
        )
        common = {
            "start_time": "09:00",
            "end_time": "12:00",
            "poster_required": False,
        }
        Workshop.objects.create(
            name="Atelier Jeux vidéo",
            location=self.loc_a,
            date=date(self.year, 1, 10),
            number_registered=10,
            number_attendees=8,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Soirée Jeux vidéo",
            location=self.loc_a,
            date=date(self.year, 2, 10),
            number_registered=5,
            number_attendees=4,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Découverte Canva",
            location=self.loc_a,
            date=date(self.year, 3, 10),
            number_registered=6,
            number_attendees=5,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Initiation Canva",
            location=self.loc_b,
            date=date(self.year, 4, 10),
            number_registered=4,
            number_attendees=4,
            class_welcome=True,
            **common,
        )
        Workshop.objects.create(
            name="Musique sur tablette",
            location=self.loc_b,
            date=date(self.year, 5, 10),
            number_registered=3,
            number_attendees=2,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Dessins sur tablette",
            location=self.loc_b,
            date=date(self.year, 6, 10),
            number_registered=2,
            number_attendees=1,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Atelier Robot",
            location=self.loc_unknown,
            date=date(self.year, 7, 10),
            number_registered=1,
            number_attendees=1,
            class_welcome=False,
            **common,
        )

    def test_global_totals(self):
        report = build_animation_report(
            Workshop.objects.filter(date__year=self.year)
        )
        self.assertTrue(report["has_data"])
        self.assertEqual(report["totals"]["sessions"], 7)
        self.assertEqual(report["totals"]["animations"], 5)
        self.assertEqual(report["totals"]["registered"], 31)
        self.assertEqual(report["totals"]["attendees"], 25)
        self.assertEqual(report["totals"]["communes"], 3)
        self.assertEqual(report["totals"]["class_welcome"], 1)
        self.assertEqual(report["totals"]["classics"], 6)
        self.assertEqual(report["totals"]["class_welcome_registered"], 4)
        self.assertEqual(report["totals"]["classics_registered"], 27)
        self.assertEqual(report["totals"]["class_welcome_attendees"], 4)
        self.assertEqual(report["totals"]["classics_attendees"], 21)

    def test_groups_and_variants(self):
        report = build_animation_report(
            Workshop.objects.filter(date__year=self.year)
        )
        groups = {group["key"]: group for group in report["groups"]}
        self.assertEqual(groups["jeux video"]["sessions"], 2)
        self.assertEqual(groups["jeux video"]["registered"], 15)
        self.assertEqual(groups["jeux video"]["attendees"], 12)
        self.assertEqual(groups["jeux video"]["label"], "Jeux vidéo")
        self.assertEqual(groups["canva"]["sessions"], 2)
        self.assertEqual(groups["canva"]["label"], "Canva")
        self.assertEqual(groups["canva"]["registered"], 10)
        self.assertEqual(groups["canva"]["attendees"], 9)
        self.assertEqual(
            groups["canva"]["communes"], ["Avesnes", "Fourmies"]
        )
        self.assertIn("Découverte Canva", groups["canva"]["variants"])
        self.assertIn("Initiation Canva", groups["canva"]["variants"])
        self.assertIn(
            "jeux video", {group["key"] for group in report["merged_groups"]}
        )
        self.assertIn(
            "canva", {group["key"] for group in report["merged_groups"]}
        )

    def test_by_commune_totals_and_animations(self):
        report = build_animation_report(
            Workshop.objects.filter(date__year=self.year)
        )
        by_city = {row["commune"]: row for row in report["by_commune"]}
        self.assertEqual(by_city["Avesnes"]["total_ateliers"], 3)
        self.assertEqual(by_city["Avesnes"]["animations_count"], 2)
        self.assertEqual(by_city["Fourmies"]["total_ateliers"], 3)
        self.assertEqual(by_city["Fourmies"]["animations_count"], 3)
        self.assertEqual(by_city["Non défini"]["total_ateliers"], 1)
        self.assertEqual(
            sum(row["registered"] for row in report["by_commune"]), 31
        )
        self.assertEqual(
            sum(row["attendees"] for row in report["by_commune"]), 25
        )
        self.assertEqual(
            sum(len(row["animations"]) for row in report["by_commune"]),
            6,
        )

    def test_empty_report(self):
        report = build_animation_report(Workshop.objects.none())
        self.assertFalse(report["has_data"])
        self.assertEqual(report["groups"], [])
        self.assertEqual(report["by_commune"], [])
        self.assertEqual(report["totals"]["sessions"], 0)
        self.assertEqual(report["totals"]["animations"], 0)


class WorkshopReportViewTests(TestCase):
    """Tests de la page rapport et de l'export DOCX."""

    def setUp(self):
        cache.clear()
        self.year = 2025
        self.loc_a = Location.objects.create(
            name="Lieu A", address="1 Rue", city="Avesnes", zip_code="59440"
        )
        self.loc_b = Location.objects.create(
            name="Lieu B", address="2 Rue", city="Fourmies", zip_code="59610"
        )
        common = {
            "start_time": "09:00",
            "end_time": "12:00",
            "poster_required": False,
        }
        Workshop.objects.create(
            name="Découverte Canva",
            location=self.loc_a,
            date=date(self.year, 1, 10),
            number_registered=6,
            number_attendees=5,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Initiation Canva",
            location=self.loc_a,
            date=date(self.year, 2, 10),
            number_registered=4,
            number_attendees=3,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Atelier Jeux vidéo",
            location=self.loc_b,
            date=date(self.year, 3, 10),
            number_registered=10,
            number_attendees=8,
            class_welcome=False,
            **common,
        )
        Workshop.objects.create(
            name="Atelier Jeux vidéo (Minecraft, FC 27, Just Dance...)",
            location=self.loc_b,
            date=date(self.year, 4, 10),
            number_registered=5,
            number_attendees=4,
            class_welcome=True,
            **common,
        )
        self.staff = User.objects.create_user(
            username="report_staff", password="pass", is_staff=True
        )
        self.basic = User.objects.create_user(
            username="report_basic", password="pass"
        )

    def tearDown(self):
        cache.clear()

    def login_staff(self):
        self.client.login(username="report_staff", password="pass")

    def test_report_page_returns_200_and_contains_sections(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report", args=[self.year])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "workshop/workshop_report.html")
        self.assertContains(response, "Rapport complet des ateliers")
        self.assertContains(response, "Résumé par commune et animations")
        self.assertContains(response, "Découverte Canva")
        self.assertContains(response, "Atelier Jeux vidéo")
        self.assertIn("animation_report", response.context)
        self.assertEqual(
            response.context["animation_report"]["totals"]["sessions"], 4
        )

    def test_report_requires_permission(self):
        response = self.client.get(
            reverse("workshop_report", args=[self.year])
        )
        self.assertEqual(response.status_code, 302)
        self.client.login(username="report_basic", password="pass")
        response = self.client.get(
            reverse("workshop_report", args=[self.year])
        )
        self.assertEqual(response.status_code, 302)

    def test_comm_group_allowed(self):
        group, _ = Group.objects.get_or_create(name="communication")
        self.basic.groups.add(group)
        self.client.login(username="report_basic", password="pass")
        response = self.client.get(
            reverse("workshop_report", args=[self.year])
        )
        self.assertEqual(response.status_code, 200)

    def test_report_city_filter(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report", args=[self.year]),
            {"city": "Avesnes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_city"], "Avesnes")
        by_commune = response.context["animation_report"]["by_commune"]
        self.assertEqual([row["commune"] for row in by_commune], ["Avesnes"])
        self.assertEqual(
            response.context["animation_report"]["totals"]["sessions"], 2
        )
        self.assertContains(response, "Découverte Canva")
        self.assertNotContains(response, "Atelier Jeux vidéo")

    def test_report_query_preserved(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report", args=[self.year]),
            {"city": "Avesnes", "class_welcome": "no"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["report_query"],
            "city=Avesnes&class_welcome=no",
        )
        self.assertContains(response, "city=Avesnes")

    def test_report_charts_payload(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report", args=[self.year])
        )
        charts = response.context["report_charts"]
        self.assertEqual(len(charts["monthly"]["labels"]), 12)
        self.assertEqual(len(charts["types"]["values"]), 2)
        self.assertEqual(len(charts["communes"]["labels"]), 2)
        self.assertEqual(len(charts["animations"]["labels"]), 2)

    def test_report_month_filter_is_consistent(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report", args=[self.year]),
            {"month": "3"},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.context["report_monthly_rows"]
        self.assertEqual(rows[2]["count"], 1)
        self.assertEqual(
            rows[2]["classic_count"] + rows[2]["class_count"], 1
        )
        self.assertEqual(rows[0]["count"], 0)
        self.assertEqual(
            rows[0]["classic_count"] + rows[0]["class_count"], 0
        )

    def test_report_docx_export(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report_export", args=[self.year])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document",
        )
        self.assertIn(
            f"rapport_ateliers_{self.year}.docx",
            response["Content-Disposition"],
        )
        self.assertTrue(response.content.startswith(b"PK"))

        document = Document(BytesIO(response.content))
        paragraphs = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
        self.assertIn("Rapport complet", paragraphs)
        self.assertIn("Résumé par commune et animations", paragraphs)
        self.assertGreaterEqual(len(document.tables), 5)
        self.assertGreaterEqual(len(document.inline_shapes), 3)

        headers = [
            [cell.text for cell in table.rows[0].cells]
            for table in document.tables
        ]
        self.assertTrue(any("Commune" in row for row in headers))
        self.assertTrue(any("Animation" in row for row in headers))

    def test_docx_export_city_filename(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report_export", args=[self.year]),
            {"city": "Avesnes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f"rapport_ateliers_avesnes_{self.year}.docx",
            response["Content-Disposition"],
        )

    def test_empty_year_report_does_not_500(self):
        self.login_staff()
        response = self.client.get(
            reverse("workshop_report", args=[1999])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune donnée")
        response = self.client.get(
            reverse("workshop_report_export", args=[1999])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"PK"))


class ReportChartTests(SimpleTestCase):
    """Tests de génération des graphiques PNG."""

    def test_monthly_chart_is_png(self):
        monthly = [
            {"label": "Jan", "count": 2},
            {"label": "Fév", "count": 1},
        ]
        month_types = [
            {"classic_count": 1, "class_count": 1},
            {"classic_count": 1, "class_count": 0},
        ]
        buffer = render_monthly_chart(
            monthly, month_types, "Ateliers par mois"
        )
        self.assertTrue(buffer.getvalue().startswith(b"\x89PNG\r\n\x1a\n"))
        image = Image.open(buffer)
        self.assertEqual(image.format, "PNG")
        self.assertGreater(image.width, 0)

    def test_empty_chart_is_png(self):
        buffer = render_monthly_chart([], [], "Aucune donnée")
        self.assertTrue(buffer.getvalue().startswith(b"\x89PNG\r\n\x1a\n"))
        image = Image.open(buffer)
        self.assertEqual(image.format, "PNG")

    def test_animations_chart_is_png(self):
        groups = [
            {"label": "Jeux vidéo", "sessions": 10},
            {"label": "Canva", "sessions": 2},
        ]
        buffer = render_animations_chart(groups, "Top animations")
        self.assertTrue(buffer.getvalue().startswith(b"\x89PNG\r\n\x1a\n"))


class WorkshopNameNormalizationTests(SimpleTestCase):
    """Tests de normalisation et de choix des noms canoniques."""

    def test_case_accents_spaces_and_punctuation_are_equivalent(self):
        variants = [
            "Atelier Jeux vidéo",
            "atelier jeux video",
            "ATELIER JEUX-VIDÉO",
            "Atelier  Jeux   vidéo !",
        ]
        self.assertEqual(
            {normalize_workshop_name(variant) for variant in variants},
            {"atelier jeux video"},
        )

    def test_plural_and_format_variants_remain_distinct(self):
        self.assertNotEqual(
            normalize_workshop_name("Atelier Robot"),
            normalize_workshop_name("Atelier Robots"),
        )
        self.assertNotEqual(
            normalize_workshop_name("Découverte Canva"),
            normalize_workshop_name("Initiation Canva"),
        )

    def test_clean_display_name_keeps_case_and_punctuation(self):
        self.assertEqual(
            clean_display_name("  Atelier   Jeux  vidéo !  "),
            "Atelier Jeux vidéo !",
        )

    def test_build_catalog_plan_uses_frequency_then_shortest(self):
        plan = build_catalog_plan(
            {
                "Atelier jeux vidéo": 2,
                "Atelier Jeux vidéo": 10,
                "Just dance": 1,
                "Just Dance": 2,
            }
        )
        by_key = {key: canonical for canonical, key in plan}
        self.assertEqual(by_key["atelier jeux video"], "Atelier Jeux vidéo")
        self.assertEqual(by_key["just dance"], "Just Dance")

    def test_build_catalog_plan_shortest_wins_on_tie(self):
        plan = build_catalog_plan(
            {
                "Dessins sur tablette (Spécial noël)": 1,
                "Dessins sur tablette spécial noël": 1,
            }
        )
        by_key = {key: canonical for canonical, key in plan}
        self.assertEqual(
            by_key["dessins sur tablette special noel"],
            "Dessins sur tablette spécial noël",
        )

    def test_build_catalog_plan_skips_empty_names(self):
        self.assertEqual(build_catalog_plan({"!!!": 2, "   ": 1}), [])


class WorkshopNameModelTests(TestCase):
    """Tests du modèle de liste des noms d'ateliers."""

    def test_save_computes_normalized_and_cleans_name(self):
        entry = WorkshopName.objects.create(
            name="  Atelier   Jeux vidéo "
        )
        self.assertEqual(entry.name, "Atelier Jeux vidéo")
        self.assertEqual(entry.normalized, "atelier jeux video")

    def test_clean_rejects_duplicate_normalized(self):
        WorkshopName.objects.create(name="Atelier Jeux vidéo")
        duplicate = WorkshopName(name="atelier jeux video")
        with self.assertRaises(ValidationError) as context:
            duplicate.full_clean()
        self.assertIn("existe déjà", str(context.exception))

    def test_clean_rejects_punctuation_only(self):
        entry = WorkshopName(name="!!!")
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_save_rejects_empty_normalized(self):
        with self.assertRaises(ValidationError):
            WorkshopName.objects.create(name="!!!")


class ResolveWorkshopNameTests(TestCase):
    """Tests de résolution d'un nom vers la liste canonique."""

    def test_returns_existing_entry_for_variant(self):
        existing = WorkshopName.objects.create(name="Atelier Jeux vidéo")
        resolved = resolve_workshop_name("ATELIER JEUX-VIDÉO !")
        self.assertEqual(resolved.pk, existing.pk)
        self.assertEqual(WorkshopName.objects.count(), 1)

    def test_creates_new_entry(self):
        entry = resolve_workshop_name("  Nouveau   nom  ")
        self.assertEqual(entry.name, "Nouveau nom")
        self.assertEqual(entry.normalized, "nouveau nom")

    def test_rejects_punctuation_only(self):
        with self.assertRaises(ValidationError):
            resolve_workshop_name("!!!")


class WorkshopCreateNameTests(TestCase):
    """Tests du champ nom dans la création d'atelier."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="name_admin", password="pass", is_staff=True
        )
        self.client.login(username="name_admin", password="pass")

    def post_workshop(self, name):
        return self.client.post(
            reverse("workshop_create"),
            {
                "name": name,
                "location": self.location.pk,
                "date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "12:00",
            },
            follow=True,
        )

    def test_new_name_is_added_to_catalog(self):
        response = self.post_workshop("Atelier Test Unique")
        self.assertRedirects(response, reverse("workshop_list"))
        self.assertTrue(
            WorkshopName.objects.filter(
                normalized="atelier test unique"
            ).exists()
        )
        self.assertTrue(
            Workshop.objects.filter(name="Atelier Test Unique").exists()
        )

    def test_existing_variant_reuses_canonical_name(self):
        WorkshopName.objects.create(name="Atelier Jeux vidéo")
        response = self.post_workshop("atelier jeux video")
        self.assertContains(response, "Nom existant réutilisé")
        self.assertTrue(
            Workshop.objects.filter(name="Atelier Jeux vidéo").exists()
        )
        self.assertEqual(WorkshopName.objects.count(), 1)

    def test_whitespace_is_normalized(self):
        self.post_workshop("  Atelier   Test  ")
        self.assertTrue(Workshop.objects.filter(name="Atelier Test").exists())
        self.assertTrue(
            WorkshopName.objects.filter(normalized="atelier test").exists()
        )

    def test_punctuation_only_name_rejected(self):
        response = self.post_workshop("!!!")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "au moins une lettre")
        self.assertFalse(Workshop.objects.exists())

    def test_form_displays_datalist_and_help(self):
        WorkshopName.objects.create(name="Atelier Jeux vidéo")
        response = self.client.get(reverse("workshop_create"))
        self.assertContains(response, 'id="workshop-name-options"')
        self.assertContains(response, 'value="Atelier Jeux vidéo"')
        self.assertContains(response, 'list="workshop-name-options"')
        self.assertContains(response, 'aria-describedby="id_name_help id_name_error"')
        self.assertContains(response, "Choisissez un nom existant")


class WorkshopUpdateNameTests(TestCase):
    """Tests du champ nom dans la modification d'atelier."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.workshop = Workshop.objects.create(
            name="Ancien nom",
            location=self.location,
            date=date(2026, 6, 15),
            start_time="09:00",
            end_time="12:00",
            poster_required=False,
        )
        self.user = User.objects.create_user(
            username="update_name_admin", password="pass", is_staff=True
        )
        self.client.login(username="update_name_admin", password="pass")

    def test_existing_variant_reuses_canonical_name(self):
        WorkshopName.objects.create(name="Atelier Jeux vidéo")
        response = self.client.post(
            reverse("workshop_update", args=[self.workshop.pk]),
            {
                "name": "atelier jeux video",
                "location": self.location.pk,
                "date": "2026-06-15",
                "start_time": "09:00",
                "end_time": "12:00",
            },
            follow=True,
        )
        self.workshop.refresh_from_db()
        self.assertEqual(self.workshop.name, "Atelier Jeux vidéo")
        self.assertContains(response, "Nom existant réutilisé")

    def test_update_form_displays_datalist(self):
        WorkshopName.objects.create(name="Atelier Jeux vidéo")
        response = self.client.get(
            reverse("workshop_update", args=[self.workshop.pk])
        )
        self.assertContains(response, 'id="workshop-name-options"')
        self.assertContains(response, 'value="Atelier Jeux vidéo"')


class NormalizeWorkshopNamesCommandTests(TestCase):
    """Tests de la commande de nettoyage des noms existants."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        common = {
            "location": self.location,
            "date": date(2026, 6, 15),
            "start_time": "09:00",
            "end_time": "12:00",
            "poster_required": False,
        }
        for _ in range(2):
            Workshop.objects.create(name="Atelier jeux vidéo", **common)
        for _ in range(10):
            Workshop.objects.create(name="Atelier Jeux vidéo", **common)
        Workshop.objects.create(name="Just dance", **common)
        for _ in range(2):
            Workshop.objects.create(name="Just Dance", **common)
        Workshop.objects.create(name="Atelier Robot", **common)
        Workshop.objects.create(name="Atelier Robots", **common)

    def run_command(self, *args):
        output = StringIO()
        call_command("normalize_workshop_names", *args, stdout=output)
        return output.getvalue()

    def test_dry_run_does_not_write(self):
        output = self.run_command()
        self.assertIn(
            "Atelier jeux vidéo -> Atelier Jeux vidéo", output
        )
        self.assertIn("Mode diagnostic", output)
        self.assertFalse(WorkshopName.objects.exists())
        self.assertEqual(
            Workshop.objects.filter(name="Atelier jeux vidéo").count(), 2
        )

    def test_apply_creates_catalog_and_renames(self):
        output = self.run_command("--apply")
        self.assertIn("Terminé", output)
        self.assertEqual(
            Workshop.objects.filter(name="Atelier Jeux vidéo").count(), 12
        )
        self.assertEqual(
            Workshop.objects.filter(name="Just Dance").count(), 3
        )
        self.assertTrue(
            WorkshopName.objects.filter(
                normalized="atelier jeux video",
                name="Atelier Jeux vidéo",
            ).exists()
        )
        self.assertTrue(
            WorkshopName.objects.filter(normalized="atelier robot").exists()
        )
        self.assertTrue(
            WorkshopName.objects.filter(normalized="atelier robots").exists()
        )

    def test_apply_is_idempotent(self):
        self.run_command("--apply")
        output = self.run_command("--apply")
        self.assertIn("déjà alignés", output)
        self.assertEqual(WorkshopName.objects.count(), 4)


class WorkshopPunctuationNameTests(TestCase):
    """Le nom d'un atelier doit contenir un caractère utile."""

    def test_workshop_name_must_contain_alphanumeric(self):
        location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        workshop = Workshop(
            name="!!!",
            location=location,
            date=date(2026, 6, 15),
            start_time="09:00",
            end_time="12:00",
            poster_required=False,
        )
        with self.assertRaises(ValidationError):
            workshop.full_clean()


def _png_upload(filename="poster.png", color="red", size=(20, 20)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return SimpleUploadedFile(
        filename, buffer.getvalue(), content_type="image/png"
    )


class WorkshopImageTests(TestCase):
    """Tests de sauvegarde, remplacement et validation des images."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="image_admin", password="pass", is_staff=True
        )
        self.client.login(username="image_admin", password="pass")

    def post_create(self, image):
        return self.client.post(
            reverse("workshop_create"),
            {
                "name": "Atelier Image",
                "location": self.location.pk,
                "date": "2026-12-20",
                "start_time": "09:00",
                "end_time": "10:00",
                "number_registered": "0",
                "number_attendees": "0",
                "image": image,
            },
            follow=True,
        )

    def post_update(self, workshop, image):
        return self.client.post(
            reverse("workshop_update", args=[workshop.pk]),
            {
                "name": workshop.name,
                "location": self.location.pk,
                "date": "2026-12-20",
                "start_time": "09:00",
                "end_time": "10:00",
                "number_registered": "0",
                "number_attendees": "0",
                "image": image,
            },
            follow=True,
        )

    def test_create_stores_one_randomized_image(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.post_create(_png_upload())
            self.assertEqual(response.status_code, 200)
            workshop = Workshop.objects.get(name="Atelier Image")
            self.assertRegex(
                workshop.image.name,
                r"^ateliers_images/[0-9a-f]{32}\.png$",
            )
            self.assertTrue(
                workshop.image.storage.exists(workshop.image.name)
            )

    def test_create_resizes_large_image(self):
        buffer = BytesIO()
        Image.new("RGB", (3000, 1200), "green").save(
            buffer, format="JPEG"
        )
        upload = SimpleUploadedFile(
            "large.jpg", buffer.getvalue(), content_type="image/jpeg"
        )
        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.post_create(upload)
            self.assertEqual(response.status_code, 200)
            workshop = Workshop.objects.get(name="Atelier Image")
            with Image.open(workshop.image.path) as image:
                self.assertLessEqual(max(image.size), 1920)

    def test_update_deletes_previous_image(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            self.post_create(_png_upload())
            workshop = Workshop.objects.get(name="Atelier Image")
            old_name = workshop.image.name
            old_storage = workshop.image.storage

            with self.captureOnCommitCallbacks(execute=True):
                response = self.post_update(
                    workshop, _png_upload("new.png", "blue")
                )
            self.assertEqual(response.status_code, 200)
            workshop.refresh_from_db()
            self.assertNotEqual(workshop.image.name, old_name)
            self.assertFalse(old_storage.exists(old_name))
            self.assertTrue(
                workshop.image.storage.exists(workshop.image.name)
            )

    def test_invalid_image_content_is_rejected(self):
        response = self.post_create(
            SimpleUploadedFile(
                "bad.png", b"not-an-image", content_type="image/png"
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Workshop.objects.filter(name="Atelier Image").exists())
        self.assertIn("image", response.context["form"].errors)

    def test_update_delete_checkbox_removes_image_and_file(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            self.post_create(_png_upload())
            workshop = Workshop.objects.get(name="Atelier Image")
            old_name = workshop.image.name
            storage = workshop.image.storage

            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("workshop_update", args=[workshop.pk]),
                    {
                        "name": workshop.name,
                        "location": self.location.pk,
                        "date": "2026-12-20",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "number_registered": "0",
                        "number_attendees": "0",
                        "DELETE": "on",
                    },
                    follow=True,
                )
            self.assertEqual(response.status_code, 200)
            workshop.refresh_from_db()
            self.assertFalse(workshop.image)
            self.assertFalse(storage.exists(old_name))

    def test_image_size_validator_rejects_large_file(self):
        large = SimpleUploadedFile(
            "large.png",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_image_size(large)


class WorkshopParticipantDefaultsTests(TestCase):
    """Tests des valeurs par défaut et limites des participants."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )

    def form_data(self, **overrides):
        data = {
            "name": "Atelier Participants",
            "location": self.location.pk,
            "date": "2026-12-20",
            "start_time": "09:00",
            "end_time": "10:00",
            "number_registered": "",
            "number_attendees": "",
        }
        data.update(overrides)
        return data

    def test_blank_participants_default_to_zero(self):
        form = WorkshopForm(data=self.form_data())
        self.assertTrue(form.is_valid(), form.errors)
        workshop = form.save()
        self.assertEqual(workshop.number_registered, 0)
        self.assertEqual(workshop.number_attendees, 0)

    def test_negative_participants_are_rejected(self):
        form = WorkshopForm(
            data=self.form_data(
                number_registered="-2", number_attendees="-1"
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("number_registered", form.errors)
        self.assertIn("number_attendees", form.errors)


class PosterNotificationTests(TestCase):
    """Tests de l'envoi unique de la demande d'affiche."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="poster_admin", password="pass", is_staff=True
        )
        self.client.login(username="poster_admin", password="pass")

    def data(self, name="Atelier Affiche", poster_required="on"):
        return {
            "name": name,
            "location": self.location.pk,
            "date": "2026-12-20",
            "start_time": "09:00",
            "end_time": "10:00",
            "poster_required": poster_required,
        }

    def test_create_sends_one_request(self):
        with patch("workshop.views.notify_poster_request") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("workshop_create"),
                    self.data(),
                    follow=True,
                )
        self.assertEqual(response.status_code, 200)
        notify.assert_called_once()

    def test_update_does_not_resend_unchanged_request(self):
        workshop = Workshop.objects.create(
            name="Atelier Affiche",
            location=self.location,
            date=date(2026, 12, 20),
            start_time="09:00",
            end_time="10:00",
            poster_required=True,
        )
        with patch("workshop.views.notify_poster_request") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("workshop_update", args=[workshop.pk]),
                    self.data(),
                    follow=True,
                )
        self.assertEqual(response.status_code, 200)
        notify.assert_not_called()

    def test_update_sends_when_request_turns_on(self):
        workshop = Workshop.objects.create(
            name="Atelier Affiche",
            location=self.location,
            date=date(2026, 12, 20),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
        )
        with patch("workshop.views.notify_poster_request") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("workshop_update", args=[workshop.pk]),
                    self.data(),
                    follow=True,
                )
        self.assertEqual(response.status_code, 200)
        notify.assert_called_once()


class SharedWorkshopFormTemplateTests(TestCase):
    """Tests du template unique et des attributs d'accessibilité."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="form_admin", password="pass", is_staff=True
        )
        self.client.login(username="form_admin", password="pass")

    def test_create_uses_shared_template_and_controls(self):
        response = self.client.get(reverse("workshop_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "workshop/workshop_form.html")
        self.assertContains(response, 'class="form-section"')
        self.assertContains(response, 'id="imagePreview"')
        self.assertContains(response, "data-stepper-target")
        self.assertContains(response, "Champs obligatoires")
        self.assertContains(response, "Annuler")
        self.assertContains(response, "id_name_help")

    def test_update_shows_edit_actions_and_preview(self):
        workshop = Workshop.objects.create(
            name="Atelier Modif",
            location=self.location,
            date=date(2026, 12, 20),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
        )
        response = self.client.get(
            reverse("workshop_update", args=[workshop.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "workshop/workshop_form.html")
        self.assertContains(response, "Mettre à jour")
        self.assertContains(response, "id=\"imagePreview\"")

    def test_invalid_form_shows_error_summary_and_associations(self):
        response = self.client.post(
            reverse("workshop_create"),
            {"name": "", "date": "", "start_time": "", "end_time": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-error-summary")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(
            response, 'aria-describedby="id_name_help id_name_error"'
        )


class WorkshopPosterFormImageTests(TestCase):
    """Tests de remplacement/suppression d'image via le formulaire affiche."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="poster_image_admin", password="pass", is_staff=True
        )

    def make_request(self):
        request = RequestFactory().post("/")
        request.user = self.user
        return request

    def make_workshop(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            return Workshop.objects.create(
                name="Atelier Affiche Image",
                location=self.location,
                date=date(2026, 12, 20),
                start_time="09:00",
                end_time="10:00",
                poster_required=True,
                image=_png_upload(),
            )

    def test_delete_checkbox_removes_image_and_file(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            workshop = self.make_workshop()
            old_name = workshop.image.name
            storage = workshop.image.storage
            form = WorkshopPosterForm(
                {"DELETE": "on"},
                instance=workshop,
                request=self.make_request(),
            )
            self.assertTrue(form.is_valid(), form.errors)
            with self.captureOnCommitCallbacks(execute=True):
                form.save()
            workshop.refresh_from_db()
            self.assertFalse(workshop.image)
            self.assertFalse(storage.exists(old_name))

    def test_replacement_deletes_old_file(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            workshop = self.make_workshop()
            old_name = workshop.image.name
            storage = workshop.image.storage
            form = WorkshopPosterForm(
                {},
                files={"image": _png_upload("new-poster.png", "blue")},
                instance=workshop,
                request=self.make_request(),
            )
            self.assertTrue(form.is_valid(), form.errors)
            with self.captureOnCommitCallbacks(execute=True):
                form.save()
            workshop.refresh_from_db()
            self.assertNotEqual(workshop.image.name, old_name)
            self.assertFalse(storage.exists(old_name))
            self.assertTrue(storage.exists(workshop.image.name))


class WorkshopConflictTests(TestCase):
    """Tests de détection des conflits de lieu et de créneau."""

    def setUp(self):
        self.loc_a = Location.objects.create(
            name="Lieu A", address="1 Rue", city="Avesnes", zip_code="59440"
        )
        self.loc_b = Location.objects.create(
            name="Lieu B", address="2 Rue", city="Fourmies", zip_code="59610"
        )
        self.existing = Workshop.objects.create(
            name="Atelier existant",
            location=self.loc_a,
            date=date(2026, 12, 20),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
        )

    def form_data(self, **overrides):
        data = {
            "name": "Nouvel atelier",
            "location": self.loc_a.pk,
            "date": "2026-12-20",
            "start_time": "09:30",
            "end_time": "10:30",
        }
        data.update(overrides)
        return data

    def test_overlapping_slot_is_rejected(self):
        form = WorkshopForm(data=self.form_data())
        self.assertFalse(form.is_valid())
        self.assertIn("existe déjà", " ".join(form.non_field_errors()))

    def test_adjacent_slot_is_allowed(self):
        form = WorkshopForm(
            data=self.form_data(start_time="10:00", end_time="11:00")
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_other_location_is_allowed(self):
        form = WorkshopForm(data=self.form_data(location=self.loc_b.pk))
        self.assertTrue(form.is_valid(), form.errors)

    def test_update_of_same_workshop_is_allowed(self):
        form = WorkshopForm(
            data=self.form_data(name=self.existing.name),
            instance=self.existing,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_update_other_fields_of_conflicting_workshop_is_allowed(self):
        Workshop.objects.create(
            name="Autre atelier en conflit",
            location=self.loc_a,
            date=date(2026, 12, 20),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
        )
        form = WorkshopForm(
            data=self.form_data(
                name="Nom modifié",
                start_time="09:00",
                end_time="10:00",
            ),
            instance=self.existing,
        )
        self.assertTrue(form.is_valid(), form.errors)
        workshop = form.save()
        self.assertEqual(workshop.name, "Nom modifié")
        self.assertEqual(workshop.date, date(2026, 12, 20))

    def test_multi_day_overlap_is_detected(self):
        self.existing.date_end = date(2026, 12, 22)
        self.existing.save()
        form = WorkshopForm(
            data=self.form_data(date="2026-12-21")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("existe déjà", " ".join(form.non_field_errors()))


class WorkshopDuplicateTests(TestCase):
    """Tests de duplication d'un atelier."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.source = Workshop.objects.create(
            name="Atelier à dupliquer",
            location=self.location,
            date=date(2026, 12, 20),
            start_time="09:00",
            end_time="10:00",
            poster_required=True,
            class_welcome=True,
            observations="À reprendre",
            number_registered=12,
            number_attendees=10,
        )
        self.source.refresh_from_db()
        self.user = User.objects.create_user(
            username="duplicate_admin", password="pass", is_staff=True
        )
        self.client.login(username="duplicate_admin", password="pass")

    def test_duplicate_redirects_to_prefilled_create(self):
        response = self.client.get(
            reverse("workshop_duplicate", args=[self.source.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/atelier/ajout/?from={self.source.pk}", response.url
        )

        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["name"], self.source.name)
        self.assertEqual(form.initial["location"], self.location)
        self.assertEqual(form.initial["start_time"], self.source.start_time)
        self.assertEqual(form.initial["end_time"], self.source.end_time)
        self.assertTrue(form.initial["poster_required"])
        self.assertTrue(form.initial["class_welcome"])
        self.assertEqual(form.initial["number_registered"], 0)
        self.assertEqual(form.initial["number_attendees"], 0)
        self.assertNotIn("date", form.initial)

    def test_duplicate_requires_permission(self):
        self.client.logout()
        response = self.client.get(
            reverse("workshop_duplicate", args=[self.source.pk])
        )
        self.assertEqual(response.status_code, 302)


class WorkshopSaveAndAddTests(TestCase):
    """Tests du bouton Enregistrer et ajouter un autre."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="save_add_admin", password="pass", is_staff=True
        )
        self.client.login(username="save_add_admin", password="pass")

    def data(self):
        return {
            "name": "Atelier Série",
            "location": self.location.pk,
            "date": "2026-12-20",
            "start_time": "09:00",
            "end_time": "10:00",
            "save_and_add": "1",
        }

    def test_redirects_to_prefilled_create(self):
        response = self.client.post(
            reverse("workshop_create"), self.data()
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"location={self.location.pk}", response.url)
        self.assertIn("date=2026-12-20", response.url)
        self.assertTrue(Workshop.objects.filter(name="Atelier Série").exists())

        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["location"], self.location)
        self.assertEqual(form.initial["date"], date(2026, 12, 20))


class WorkshopLot2TemplateTests(TestCase):
    """Tests des éléments UX du lot 2."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.location = Location.objects.create(
            name="Loc", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="lot2_admin", password="pass", is_staff=True
        )
        self.client.login(username="lot2_admin", password="pass")

    def test_create_page_has_preview_sticky_actions_and_location_link(self):
        response = self.client.get(reverse("workshop_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="previewName"')
        self.assertContains(response, "data-unsaved-warning")
        self.assertContains(response, "form-actions-sticky")
        self.assertContains(response, 'name="save_and_add"')
        self.assertContains(response, "Ajouter un lieu")
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, "Actualiser")
        self.assertContains(response, "/atelier/lieux/options/")

    def test_create_page_has_recurrence_without_diffusion_or_status(self):
        response = self.client.get(reverse("workshop_create"))
        self.assertContains(response, 'id="id_recurrence"')
        self.assertContains(response, 'id="id_recurrence_count"')
        self.assertNotContains(response, 'id="id_status"')
        for channel in ("facebook", "instagram", "mail", "portail", "vdn"):
            self.assertNotContains(response, f'id="id_{channel}"')

    def test_location_options_endpoint_preserves_selection(self):
        other = Location.objects.create(
            name="Autre lieu",
            address="2 Rue",
            city="Fourmies",
            zip_code="59610",
        )
        response = self.client.get(
            reverse("workshop_location_options"),
            {"location": self.location.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.location.name)
        self.assertContains(response, other.name)
        self.assertContains(
            response,
            f'<option value="{self.location.pk}" selected>',
            html=False,
        )

    def test_update_page_has_delete_image_control(self):
        with override_settings(MEDIA_ROOT=self.media_root):
            workshop = Workshop.objects.create(
                name="Atelier Lot 2",
                location=self.location,
                date=date(2026, 12, 20),
                start_time="09:00",
                end_time="10:00",
                poster_required=False,
                image=_png_upload(),
            )
            response = self.client.get(
                reverse("workshop_update", args=[workshop.pk])
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="DELETE"')
        self.assertContains(response, "image actuelle")
        self.assertNotContains(response, 'name="save_and_add"')


class RecurrenceDatesTests(SimpleTestCase):
    """Tests du calcul des dates d'une série."""

    def test_none_returns_single_occurrence(self):
        start = date(2026, 3, 2)
        self.assertEqual(
            occurrence_dates(start, None, RECURRENCE_NONE, 5),
            [(start, None)],
        )

    def test_weekly_and_biweekly(self):
        start = date(2026, 3, 2)
        weekly = occurrence_dates(start, None, RECURRENCE_WEEKLY, 3)
        self.assertEqual(
            [d for d, _ in weekly],
            [date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16)],
        )
        biweekly = occurrence_dates(start, None, RECURRENCE_BIWEEKLY, 3)
        self.assertEqual(
            [d for d, _ in biweekly],
            [date(2026, 3, 2), date(2026, 3, 16), date(2026, 3, 30)],
        )

    def test_monthly_clamps_short_months(self):
        occurrences = occurrence_dates(
            date(2026, 1, 31), None, RECURRENCE_MONTHLY, 3
        )
        self.assertEqual(
            [d for d, _ in occurrences],
            [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)],
        )

    def test_multi_day_end_date_is_shifted(self):
        occurrences = occurrence_dates(
            date(2026, 1, 10),
            date(2026, 1, 12),
            RECURRENCE_WEEKLY,
            2,
        )
        self.assertEqual(occurrences[1], (date(2026, 1, 17), date(2026, 1, 19)))


class WorkshopRecurrenceTests(TestCase):
    """Tests de création d'une série depuis le formulaire."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Lieu série", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="series_admin", password="pass", is_staff=True
        )
        self.client.login(username="series_admin", password="pass")

    def data(self, **overrides):
        payload = {
            "name": "Atelier série",
            "location": self.location.pk,
            "date": "2026-03-02",
            "start_time": "09:00",
            "end_time": "10:00",
            "number_registered": "0",
            "number_attendees": "0",
            "recurrence": RECURRENCE_WEEKLY,
            "recurrence_count": "3",
        }
        payload.update(overrides)
        return payload

    def test_create_weekly_series(self):
        response = self.client.post(
            reverse("workshop_create"), self.data()
        )
        self.assertRedirects(response, reverse("workshop_list"))
        workshops = list(Workshop.objects.order_by("series_index"))
        self.assertEqual(len(workshops), 3)
        self.assertEqual(
            [w.date for w in workshops],
            [date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16)],
        )
        self.assertEqual(len({w.series for w in workshops}), 1)
        self.assertIsNotNone(workshops[0].series)
        self.assertEqual(
            [w.series_index for w in workshops], [1, 2, 3]
        )
        self.assertEqual(workshops[0].created_by, self.user)
        self.assertEqual(workshops[0].updated_by, self.user)

    def test_series_conflict_blocks_every_occurrence(self):
        Workshop.objects.create(
            name="Atelier existant",
            location=self.location,
            date=date(2026, 3, 9),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
        )
        response = self.client.post(
            reverse("workshop_create"), self.data()
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertTrue(form.errors)
        self.assertIn("09/03/2026", str(form.non_field_errors()))
        self.assertEqual(Workshop.objects.count(), 1)

    def test_save_and_add_is_ignored_for_a_series(self):
        response = self.client.post(
            reverse("workshop_create"),
            self.data(save_and_add="1"),
        )
        self.assertRedirects(response, reverse("workshop_list"))
        self.assertEqual(Workshop.objects.count(), 3)

    def test_overlapping_multi_day_series_is_rejected(self):
        response = self.client.post(
            reverse("workshop_create"),
            self.data(date_end="2026-03-10"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("chevauche", str(response.context["form"].errors))
        self.assertFalse(Workshop.objects.exists())

    def test_single_workshop_has_no_series(self):
        self.client.post(
            reverse("workshop_create"),
            self.data(recurrence=RECURRENCE_NONE),
        )
        workshop = Workshop.objects.get()
        self.assertIsNone(workshop.series)
        self.assertIsNone(workshop.series_index)

    def test_detail_mentions_series_size(self):
        self.client.post(
            reverse("workshop_create"), self.data()
        )
        first = Workshop.objects.order_by("series_index").first()
        response = self.client.get(
            reverse("workshop_detail", args=[first.pk])
        )
        self.assertContains(response, "Série de 3 ateliers")


class WorkshopAuditTests(TestCase):
    """Tests des champs d'audit et de la séparation avec l'affiche."""

    def setUp(self):
        self.location = Location.objects.create(
            name="Lieu audit", address="1 Rue", city="Paris", zip_code="75000"
        )
        self.user = User.objects.create_user(
            username="audit_admin", password="pass", is_staff=True
        )
        self.client.login(username="audit_admin", password="pass")

    def data(self, **overrides):
        payload = {
            "name": "Atelier audit",
            "location": self.location.pk,
            "date": "2026-04-02",
            "start_time": "09:00",
            "end_time": "10:00",
            "number_registered": "0",
            "number_attendees": "0",
        }
        payload.update(overrides)
        return payload

    def test_create_sets_audit_users(self):
        response = self.client.post(
            reverse("workshop_create"), self.data()
        )
        self.assertRedirects(response, reverse("workshop_list"))
        workshop = Workshop.objects.get()
        self.assertEqual(workshop.created_by, self.user)
        self.assertEqual(workshop.updated_by, self.user)

    def test_update_sets_updated_by(self):
        workshop = Workshop.objects.create(
            name="Atelier audit",
            location=self.location,
            date=date(2026, 4, 2),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
        )
        response = self.client.post(
            reverse("workshop_update", args=[workshop.pk]),
            self.data(),
        )
        self.assertRedirects(response, reverse("workshop_list"))
        workshop.refresh_from_db()
        self.assertEqual(workshop.updated_by, self.user)

    def test_detail_shows_audit_dates(self):
        workshop = Workshop.objects.create(
            name="Atelier audit",
            location=self.location,
            date=date(2026, 4, 2),
            start_time="09:00",
            end_time="10:00",
            poster_required=False,
            created_by=self.user,
            updated_by=self.user,
        )
        response = self.client.get(
            reverse("workshop_detail", args=[workshop.pk])
        )
        self.assertContains(response, "Créé")
        self.assertContains(response, "Modifié")

    def test_workshop_form_has_no_status_or_diffusion_fields(self):
        form = WorkshopForm()
        self.assertNotIn("status", form.fields)
        for channel in ("facebook", "instagram", "mail", "portail", "vdn"):
            self.assertNotIn(channel, form.fields)

    def test_poster_form_keeps_diffusion_channels(self):
        form = WorkshopPosterForm()
        for channel in ("facebook", "instagram", "mail", "portail", "vdn"):
            self.assertIn(channel, form.fields)


class WorkshopImageOptimizationTests(SimpleTestCase):
    """Tests de redimensionnement et de réencodage des images."""

    def make_upload(self, name, size, image_format, color="red"):
        buffer = BytesIO()
        Image.new("RGB", size, color).save(buffer, format=image_format)
        content_type = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "GIF": "image/gif",
        }[image_format]
        return SimpleUploadedFile(
            name, buffer.getvalue(), content_type=content_type
        )

    def test_large_image_is_resized(self):
        upload = self.make_upload("large.jpg", (3000, 1200), "JPEG")
        optimized = optimize_workshop_image(upload)
        self.assertEqual(optimized.name, "large.jpg")
        optimized.seek(0)
        with Image.open(optimized) as image:
            self.assertLessEqual(max(image.size), 1920)
            self.assertEqual(image.format, "JPEG")

    def test_small_image_keeps_its_name(self):
        upload = self.make_upload("small.png", (20, 20), "PNG")
        optimized = optimize_workshop_image(upload)
        self.assertEqual(optimized.name, "small.png")
        optimized.seek(0)
        with Image.open(optimized) as image:
            self.assertEqual(image.size, (20, 20))

    def test_gif_is_left_untouched(self):
        upload = self.make_upload("anim.gif", (20, 20), "GIF")
        self.assertIs(optimize_workshop_image(upload), upload)
