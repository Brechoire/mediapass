from datetime import date, time, timedelta
from calendar import monthrange
from collections import OrderedDict

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db.models import Count, Q
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import re
from .models import Workshop, WorkshopParticipant
from .forms import WorkshopForm, QuickLocationForm
from .services import NewsletterService
from visitor_tracking.models import Location as VisitorLocation


class WorkshopModelTest(TestCase):
    """Tests pour le modèle Workshop"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )

        self.workshop = Workshop.objects.create(
            title="Test Workshop",
            description="Description de test",
            start_date="2024-12-25",
            start_time="14:00",
            end_time="16:00",
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )

    def test_workshop_creation(self):
        self.assertEqual(self.workshop.title, "Test Workshop")
        self.assertEqual(self.workshop.created_by, self.user)
        self.assertTrue(self.workshop.is_all_ages)
        self.assertEqual(self.workshop.location.name, "Médiathèque")

    def test_age_range_display_tout_public(self):
        self.assertEqual(self.workshop.age_range_display, "Tout public")

    def test_age_range_display_min_max(self):
        self.workshop.is_all_ages = False
        self.workshop.min_age = 7
        self.workshop.max_age = 12
        self.workshop.save()
        self.assertEqual(self.workshop.age_range_display, "De 7 à 12 ans")

    def test_age_range_display_min_only(self):
        self.workshop.is_all_ages = False
        self.workshop.min_age = 16
        self.workshop.save()
        self.assertEqual(self.workshop.age_range_display, "À partir de 16 ans")

    def test_age_range_display_max_only(self):
        self.workshop.is_all_ages = False
        self.workshop.max_age = 65
        self.workshop.save()
        self.assertEqual(self.workshop.age_range_display, "Jusqu'à 65 ans")

    def test_is_single_day(self):
        self.assertTrue(self.workshop.is_single_day)
        self.workshop.end_date = "2024-12-26"
        self.workshop.save()
        self.assertFalse(self.workshop.is_single_day)

    def test_participants_count(self):
        WorkshopParticipant.objects.create(
            workshop=self.workshop,
            first_name="John",
            last_name="Doe",
            age=25,
            status="confirmed",
        )
        WorkshopParticipant.objects.create(
            workshop=self.workshop,
            first_name="Jane",
            last_name="Smith",
            age=30,
            status="waiting",
        )
        self.assertEqual(self.workshop.current_participants_count, 1)
        self.assertEqual(self.workshop.waiting_list_count, 1)
        self.assertEqual(self.workshop.available_spots, 9)

    def test_workshop_location_fk(self):
        """Vérifie que le lieu est bien un FK vers VisitorLocation"""
        self.assertIsInstance(self.workshop.location, VisitorLocation)
        self.assertEqual(self.workshop.location.name, "Médiathèque")

    def test_workshop_location_nullable(self):
        """Vérifie que le lieu peut être NULL"""
        workshop2 = Workshop.objects.create(
            title="Workshop sans lieu",
            description="Test",
            start_date="2024-12-25",
            start_time="14:00",
            end_time="16:00",
            location=None,
            max_participants=10,
            created_by=self.user,
        )
        self.assertIsNone(workshop2.location)

    def test_model_indexes(self):
        expected_indexes = {
            "idx_workshop_start",
            "idx_participant_ws_status",
        }
        db_indexes = set()
        for index in Workshop._meta.indexes:
            db_indexes.add(index.name)
        for index in WorkshopParticipant._meta.indexes:
            db_indexes.add(index.name)
        for expected in expected_indexes:
            self.assertIn(expected, db_indexes, f"L'index {expected} est manquant")

    def test_start_date_db_index(self):
        self.assertTrue(Workshop._meta.get_field("start_date").db_index)

    def test_end_date_db_index(self):
        self.assertTrue(Workshop._meta.get_field("end_date").db_index)

    def test_status_db_index(self):
        self.assertTrue(WorkshopParticipant._meta.get_field("status").db_index)


FUTURE_DATE = "2099-12-25"


class WorkshopFormTest(TestCase):
    """Tests pour le formulaire WorkshopForm"""

    def setUp(self):
        self.location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )

    def test_form_valid_tout_public(self):
        form_data = {
            "title": "Test Workshop",
            "description": "Description de test",
            "start_date": FUTURE_DATE,
            "start_time": "14:00",
            "end_time": "16:00",
            "location": self.location.pk,
            "max_participants": 10,
            "is_all_ages": True,
            "newsletter": True,
            "is_class_welcome": False,
            "is_single_day": True,
        }
        form = WorkshopForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_age_range(self):
        form_data = {
            "title": "Test Workshop",
            "description": "Description de test",
            "start_date": FUTURE_DATE,
            "start_time": "14:00",
            "end_time": "16:00",
            "location": self.location.pk,
            "max_participants": 10,
            "is_all_ages": False,
            "min_age": 7,
            "max_age": 12,
            "newsletter": True,
            "is_class_welcome": False,
            "is_single_day": True,
        }
        form = WorkshopForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_age_range(self):
        form_data = {
            "title": "Test Workshop",
            "description": "Description de test",
            "start_date": FUTURE_DATE,
            "start_time": "14:00",
            "end_time": "16:00",
            "location": self.location.pk,
            "max_participants": 10,
            "is_all_ages": False,
            "min_age": 15,
            "max_age": 10,
            "newsletter": True,
            "is_class_welcome": False,
            "is_single_day": True,
        }
        form = WorkshopForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "L'âge minimum ne peut pas être supérieur à l'âge maximum.",
            form.non_field_errors(),
        )

    def test_form_invalid_time_range(self):
        form_data = {
            "title": "Test Workshop",
            "description": "Description de test",
            "start_date": FUTURE_DATE,
            "start_time": "16:00",
            "end_time": "14:00",
            "location": self.location.pk,
            "max_participants": 10,
            "is_all_ages": True,
            "newsletter": True,
            "is_class_welcome": False,
            "is_single_day": True,
        }
        form = WorkshopForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "L'heure de fin doit être postérieure à l'heure de début.",
            form.non_field_errors(),
        )

    def test_form_location_queryset_active_only(self):
        """Vérifie que seuls les lieux actifs sont dans le queryset"""
        VisitorLocation.objects.create(
            name="Ludothèque", icon="bx-game", color="#10B981", is_active=True
        )
        VisitorLocation.objects.create(
            name="Ancien lieu", icon="bx-building", color="#EF4444", is_active=False
        )
        form = WorkshopForm()
        active_locations = form.fields["location"].queryset
        self.assertEqual(active_locations.count(), 2)
        self.assertNotIn("Ancien lieu", [loc.name for loc in active_locations])

    def test_form_location_empty_label(self):
        """Vérifie qu'il y a un empty_label"""
        form = WorkshopForm()
        self.assertEqual(form.fields["location"].empty_label, "Sélectionnez un lieu...")


class QuickLocationFormTest(TestCase):
    """Tests pour le formulaire QuickLocationForm"""

    def test_form_valid(self):
        form = QuickLocationForm(
            data={
                "name": "Nouveau lieu test",
                "icon": "bx-building",
                "color": "#4F46E5",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_invalid_empty_name(self):
        form = QuickLocationForm(
            data={"name": "", "icon": "bx-building", "color": "#4F46E5"}
        )
        self.assertFalse(form.is_valid())


class WorkshopViewsTest(TestCase):
    """Tests pour les vues"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )
        self.mediatheque_group = Group.objects.create(name="mediatheque")
        self.user.groups.add(self.mediatheque_group)

    def test_index_view_authenticated_mediatheque(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("library_workshops:index"))
        self.assertEqual(response.status_code, 200)

    def test_index_view_authenticated_not_mediatheque(self):
        self.user.groups.remove(self.mediatheque_group)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("library_workshops:index"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("home"))

    def test_index_view_not_authenticated(self):
        response = self.client.get(reverse("library_workshops:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("connexion", response.headers.get("Location"))

    def test_create_workshop_view_get(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("library_workshops:create_workshop"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Créer un nouvel atelier")

    def test_create_workshop_view_post_valid(self):
        self.client.login(username="testuser", password="testpass123")
        form_data = {
            "title": "Test Workshop",
            "description": "Description de test",
            "start_date": FUTURE_DATE,
            "start_time": "14:00",
            "end_time": "16:00",
            "location": self.location.pk,
            "max_participants": 10,
            "is_all_ages": True,
            "newsletter": True,
            "is_class_welcome": False,
            "is_single_day": True,
        }
        response = self.client.post(
            reverse("library_workshops:create_workshop"), form_data
        )
        self.assertRedirects(response, reverse("library_workshops:index"))
        workshop = Workshop.objects.get(title="Test Workshop")
        self.assertEqual(workshop.created_by, self.user)
        self.assertEqual(workshop.location, self.location)

    def test_access_denied_view(self):
        response = self.client.get(reverse("library_workshops:access_denied"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Accès Refusé", status_code=403)


class WorkshopOptimizationTest(TestCase):
    """Tests pour les optimisations SQL et le N+1"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.group = Group.objects.create(name="mediatheque")
        self.user.groups.add(self.group)
        self.client.login(username="testuser", password="testpass123")
        self.location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )

        for i in range(3):
            workshop = Workshop.objects.create(
                title=f"Workshop {i}",
                description=f"Description {i}",
                start_date="2025-12-25",
                start_time=f"1{i}:00",
                end_time=f"1{i+1}:00",
                location=self.location,
                max_participants=10,
                created_by=self.user,
            )
            for j in range(3):
                WorkshopParticipant.objects.create(
                    workshop=workshop,
                    first_name=f"User{j}",
                    last_name=f"Test{i}",
                    age=20 + j,
                    status="confirmed" if j < 2 else "waiting",
                )

    def test_index_view_annotates_participant_counts(self):
        """Vérifie que la vue index utilise des annotations pour éviter N+1"""
        response = self.client.get(reverse("library_workshops:index"))
        self.assertEqual(response.status_code, 200)

        workshops = response.context["workshops"]
        for w in workshops:
            self.assertTrue(
                hasattr(w, "confirmed_count"),
                "L'annotation confirmed_count est manquante",
            )
            self.assertTrue(
                hasattr(w, "waiting_count"), "L'annotation waiting_count est manquante"
            )

    def test_annotated_counts_match_property(self):
        """Vérifie que les annotations correspondent aux propriétés du modèle"""
        response = self.client.get(reverse("library_workshops:index"))
        workshops = response.context["workshops"]
        for w in workshops:
            self.assertEqual(
                w.confirmed_count,
                WorkshopParticipant.objects.filter(
                    workshop=w, status="confirmed"
                ).count(),
            )

    def test_index_select_related_location(self):
        """Vérifie que la vue index utilise select_related pour éviter N+1"""
        response = self.client.get(reverse("library_workshops:index"))
        workshops = response.context["workshops"]
        for w in workshops:
            with self.assertNumQueries(0):
                name = w.location.name


class LocationHTMXTest(TestCase):
    """Tests pour les endpoints HTMX de création de lieu"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.group = Group.objects.create(name="mediatheque")
        self.user.groups.add(self.group)
        self.client.login(username="testuser", password="testpass123")

    def test_create_location_modal_view(self):
        """Vérifie que le modal HTMX est accessible"""
        response = self.client.get(reverse("library_workshops:create_location_modal"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ajouter un lieu", response.content.decode())
        self.assertIn("quick-location-form", response.content.decode())

    def test_create_location_valid(self):
        """Vérifie la création d'un lieu via HTMX"""
        response = self.client.post(
            reverse("library_workshops:create_location"),
            {"name": "Test Location", "icon": "bx-building", "color": "#4F46E5"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["location_name"], "Test Location")
        self.assertTrue(VisitorLocation.objects.filter(name="Test Location").exists())

    def test_create_location_duplicate(self):
        """Vérifie que les doublons sont rejetés"""
        VisitorLocation.objects.create(
            name="Doublon", icon="bx-building", color="#4F46E5", user=self.user
        )
        response = self.client.post(
            reverse("library_workshops:create_location"),
            {"name": "Doublon", "icon": "bx-building", "color": "#4F46E5"},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_create_location_invalid(self):
        """Vérifie que les données invalides sont rejetées"""
        response = self.client.post(
            reverse("library_workshops:create_location"),
            {"name": "", "icon": "bx-building", "color": "#4F46E5"},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_location_not_authenticated(self):
        """Vérifie que l'authentification est requise (redirection vers login)"""
        self.client.logout()
        response = self.client.post(
            reverse("library_workshops:create_location"),
            {"name": "Test", "icon": "bx-building", "color": "#4F46E5"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("connexion", response.headers.get("Location"))

    def test_create_location_get_not_allowed(self):
        """Vérifie que GET sur create_location renvoie 405"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("library_workshops:create_location"))
        self.assertEqual(response.status_code, 405)


class WorkshopParticipantTest(TestCase):
    """Tests pour le modèle WorkshopParticipant"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )
        self.workshop = Workshop.objects.create(
            title="Test Workshop",
            description="Description de test",
            start_date="2024-12-25",
            start_time="14:00",
            end_time="16:00",
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )

    def test_participant_creation(self):
        participant = WorkshopParticipant.objects.create(
            workshop=self.workshop,
            first_name="John",
            last_name="Doe",
            age=25,
            email="john@example.com",
            status="confirmed",
            added_by=self.user,
        )
        self.assertEqual(participant.full_name, "John Doe")
        self.assertEqual(participant.age_display, "25 ans")
        self.assertEqual(participant.workshop, self.workshop)

    def test_participant_age_display_singular(self):
        participant = WorkshopParticipant.objects.create(
            workshop=self.workshop,
            first_name="Baby",
            last_name="Doe",
            age=1,
            status="confirmed",
        )
        self.assertEqual(participant.age_display, "1 an")


class SearchWorkshopTitlesViewTest(TestCase):
    """Tests pour la vue de recherche de titres d'ateliers (autocomplete)"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )
        self.mediatheque_group = Group.objects.create(name="mediatheque")
        self.user.groups.add(self.mediatheque_group)

        self.titles = [
            "Scottie GO",
            "Scottie GO Niveau 2",
            "Atelier Lecture",
            "Atelier Dessin",
            "Animation Musique",
            "Animation Danse",
            "scottie go debutant",
            "SCOTTIE GO EXPERT",
        ]
        for title in self.titles:
            Workshop.objects.create(
                title=title,
                description=f"Description for {title}",
                start_date="2025-12-25",
                start_time="14:00",
                end_time="16:00",
                location=self.location,
                max_participants=10,
                created_by=self.user,
            )

    def test_requires_login(self):
        """L'utilisateur non authentifié est redirigé"""
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "Scottie"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("connexion", response.headers.get("Location"))

    def test_requires_mediatheque_group(self):
        """L'utilisateur sans groupe mediatheque est redirigé"""
        self.user.groups.remove(self.mediatheque_group)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "Scottie"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("home"))

    def test_returns_options_for_matching_query(self):
        """Retourne des <option> pour les titres correspondant à la requête"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "Atelier"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="Atelier Dessin">')
        self.assertContains(response, '<option value="Atelier Lecture">')

    def test_empty_query_returns_no_options(self):
        """Requête vide ne retourne pas d'options"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<option")

    def test_short_query_returns_no_options(self):
        """Requête < 2 caractères ne retourne pas d'options"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "S"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<option")

    def test_no_match_returns_no_options(self):
        """Requête sans correspondance ne retourne pas d'options"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "XYZUnicorn"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<option")

    def test_case_insensitive_search(self):
        """La recherche est insensible à la casse"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "scottie"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="SCOTTIE GO EXPERT">')
        self.assertContains(response, '<option value="Scottie GO">')
        self.assertContains(response, '<option value="scottie go debutant">')

    def test_distinct_results(self):
        """Les titres en double n'apparaissent qu'une fois"""
        Workshop.objects.create(
            title="Scottie GO",
            description="Duplicate",
            start_date="2025-12-26",
            start_time="10:00",
            end_time="12:00",
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "Scottie"}
        )
        count = response.content.decode().count('<option value="Scottie GO">')
        self.assertEqual(count, 1)

    def test_max_10_results(self):
        """Limité à 10 résultats maximum"""
        for i in range(15):
            Workshop.objects.create(
                title=f"Animation Test {i}",
                description=f"Description {i}",
                start_date="2025-12-25",
                start_time="14:00",
                end_time="16:00",
                location=self.location,
                max_participants=10,
                created_by=self.user,
            )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "Animation"}
        )
        options = re.findall(r"<option[^>]*>", response.content.decode())
        self.assertLessEqual(len(options), 10)

    def test_results_ordered_alphabetically(self):
        """Les résultats sont triés alphabétiquement"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            reverse("library_workshops:search_titles"), {"title": "Scottie"}
        )
        values = re.findall(r'<option value="([^"]+)">', response.content.decode())
        self.assertEqual(values, sorted(values))


class CreateWorkshopTemplateTest(TestCase):
    """Tests pour l'intégration template de l'autocomplete"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.group = Group.objects.create(name="mediatheque")
        self.user.groups.add(self.group)
        self.client.login(username="testuser", password="testpass123")

    def test_create_form_has_datalist(self):
        """Le formulaire de création contient un datalist"""
        response = self.client.get(reverse("library_workshops:create_workshop"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<datalist id="workshop-titles">')

    def test_create_form_has_list_attribute_on_title(self):
        """Le champ titre a l'attribut list pointant vers le datalist"""
        response = self.client.get(reverse("library_workshops:create_workshop"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'list="workshop-titles"')

    def test_create_form_has_htmx_attributes(self):
        """Le champ titre a les attributs HTMX nécessaires"""
        response = self.client.get(reverse("library_workshops:create_workshop"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hx-get")
        self.assertContains(response, "hx-trigger")
        self.assertContains(response, "hx-target")
        search_url = reverse("library_workshops:search_titles")
        self.assertContains(response, search_url)

    def test_edit_form_also_has_autocomplete(self):
        """Le formulaire d'édition a aussi l'autocomplete (même template)"""
        location = VisitorLocation.objects.create(
            name="Médiathèque", icon="bx-building", color="#4F46E5"
        )
        workshop = Workshop.objects.create(
            title="Test",
            description="Test",
            start_date="2025-12-25",
            start_time="14:00",
            end_time="16:00",
            location=location,
            max_participants=10,
            created_by=self.user,
        )
        response = self.client.get(
            reverse("library_workshops:edit_workshop", args=[workshop.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'list="workshop-titles"')
        self.assertContains(response, '<datalist id="workshop-titles">')


class NewsletterServiceTest(TestCase):
    """Tests pour le NewsletterService"""

    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="testpass123")
        self.location = VisitorLocation.objects.create(
            name="Médiathèque A", icon="bx-building", color="#4F46E5", is_active=True
        )
        self.today = timezone.now().date()

    def _next_month_start(self):
        year = self.today.year
        month = self.today.month
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)

    def test_format_date_single_day(self):
        """Format 'Samedi 30 mai, 14h' pour un atelier sur un seul jour"""
        ws = Workshop(
            title="Test",
            description="Desc",
            start_date=self._next_month_start().replace(day=15),
            start_time=time(14, 0),
            end_time=time(16, 0),
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )
        result = NewsletterService.format_date(ws)
        self.assertIn("15", result)
        self.assertIn("14h", result)
        self.assertNotIn("Du ", result)

    def test_format_date_multi_day_same_month(self):
        """Format 'Du 9 au 27 juin' pour un atelier multi-jours même mois"""
        start = self._next_month_start().replace(day=9)
        end = self._next_month_start().replace(day=27)
        ws = Workshop(
            title="Expo",
            description="Desc",
            start_date=start,
            end_date=end,
            start_time=time(10, 0),
            end_time=time(18, 0),
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )
        result = NewsletterService.format_date(ws)
        self.assertIn("Du 9", result)
        self.assertIn("27", result)

    def test_format_date_hour_with_minutes(self):
        """Format '14h30' quand les minutes sont non-nulles"""
        ws = Workshop(
            title="Test",
            description="Desc",
            start_date=self._next_month_start().replace(day=5),
            start_time=time(14, 30),
            end_time=time(16, 0),
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )
        result = NewsletterService.format_date(ws)
        self.assertIn("14h30", result)

    def test_format_date_works_without_end_date(self):
        """Fonctionne quand end_date est None"""
        ws = Workshop(
            title="Test",
            description="Desc",
            start_date=self._next_month_start().replace(day=1),
            start_time=time(9, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )
        result = NewsletterService.format_date(ws)
        self.assertIn("9h", result)
        self.assertIn(str(ws.start_date.day), result)

    def test_format_text_single_workshop(self):
        """Format complet pour copie d'un atelier"""
        ws = Workshop(
            title="Atelier Test",
            description="Description de l'atelier",
            start_date=self._next_month_start().replace(day=10),
            start_time=time(14, 0),
            end_time=time(16, 0),
            location=self.location,
            max_participants=10,
            created_by=self.user,
        )
        text = NewsletterService.format_workshop_text(ws)
        self.assertIn("Atelier Test", text)
        self.assertIn("Description de l'atelier", text)
        self.assertIn("14h", text)

    def test_get_newsletter_data_next_month_only(self):
        """Seuls les ateliers du mois suivant sont retournés"""
        next_month = self._next_month_start()
        _, last_day = monthrange(next_month.year, next_month.month)
        prev_month_start = next_month - timedelta(days=10)

        Workshop.objects.create(
            title="Mois courant",
            description="Desc",
            start_date=prev_month_start,
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.user,
        )
        Workshop.objects.create(
            title="Mois prochain",
            description="Desc",
            start_date=next_month.replace(day=15),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.user,
        )

        data = NewsletterService.get_newsletter_data()
        all_workshops = []
        for loc_ws in data["grouped_workshops"].values():
            all_workshops.extend(loc_ws)
        titles = [w.title for w in all_workshops]
        self.assertIn("Mois prochain", titles)
        self.assertNotIn("Mois courant", titles)

    def test_get_newsletter_data_newsletter_false_excluded(self):
        """Les ateliers avec newsletter=False sont exclus"""
        next_month = self._next_month_start()
        Workshop.objects.create(
            title="Inclus",
            description="Desc",
            start_date=next_month.replace(day=5),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.user,
        )
        Workshop.objects.create(
            title="Exclu",
            description="Desc",
            start_date=next_month.replace(day=10),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=False,
            created_by=self.user,
        )

        data = NewsletterService.get_newsletter_data()
        all_workshops = []
        for loc_ws in data["grouped_workshops"].values():
            all_workshops.extend(loc_ws)
        titles = [w.title for w in all_workshops]
        self.assertIn("Inclus", titles)
        self.assertNotIn("Exclu", titles)

    def test_get_newsletter_data_grouped_by_user(self):
        """Les ateliers sont groupés par utilisateur médiathèque"""
        next_month = self._next_month_start()
        user2 = User.objects.create_user(
            username="mediatheque2", password="testpass123"
        )
        Workshop.objects.create(
            title="Atelier A",
            description="Desc",
            start_date=next_month.replace(day=5),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.user,
        )
        Workshop.objects.create(
            title="Atelier B",
            description="Desc",
            start_date=next_month.replace(day=6),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=user2,
        )

        data = NewsletterService.get_newsletter_data()
        self.assertIn(self.user, data["grouped_workshops"])
        self.assertIn(user2, data["grouped_workshops"])

    def test_get_newsletter_data_select_related(self):
        """Vérifie select_related pour éviter N+1 sur created_by"""
        next_month = self._next_month_start()
        Workshop.objects.create(
            title="Test",
            description="Desc",
            start_date=next_month.replace(day=5),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.user,
        )

        data = NewsletterService.get_newsletter_data()
        for user, workshops in data["grouped_workshops"].items():
            for w in workshops:
                with self.assertNumQueries(0):
                    _ = w.created_by.username

    def test_context_current_month(self):
        """Le contexte inclut le mois courant correct"""
        data = NewsletterService.get_newsletter_data()
        self.assertEqual(data["current_month"], self.today)

    def test_context_next_month(self):
        """Le contexte inclut la date de début du mois suivant"""
        data = NewsletterService.get_newsletter_data()
        self.assertEqual(data["next_month"], self._next_month_start())

    def test_december_to_january(self):
        """Teste le passage décembre → janvier"""
        next_month = self._next_month_start()
        year = next_month.year
        if next_month.month == 1:
            # décembre
            dec_start = date(year - 1, 12, 1)
            next_month_from_dec = date(year, 1, 1)
            Workshop.objects.create(
                title="Janvier",
                description="Desc",
                start_date=next_month_from_dec.replace(day=10),
                start_time=time(10, 0),
                end_time=time(12, 0),
                location=self.location,
                max_participants=10,
                newsletter=True,
                created_by=self.user,
            )
            data = NewsletterService.get_newsletter_data(
                override_date=date(year - 1, 12, 15)
            )
            all_workshops = []
            for loc_ws in data["grouped_workshops"].values():
                all_workshops.extend(loc_ws)
            self.assertEqual(len(all_workshops), 1)
            self.assertEqual(all_workshops[0].title, "Janvier")


class NewsletterViewTest(TestCase):
    """Tests pour la vue newsletter"""

    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_user(
            username="superadmin", password="testpass123", is_superuser=True
        )
        self.user = User.objects.create_user(username="normal", password="testpass123")
        self.location = VisitorLocation.objects.create(
            name="Médiathèque A", icon="bx-building", color="#4F46E5", is_active=True
        )
        self.today = timezone.now().date()

    def _next_month_start(self):
        year = self.today.year
        month = self.today.month
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)

    def test_requires_superuser(self):
        """Non-superuser est redirigé"""
        self.client.login(username="normal", password="testpass123")
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertEqual(response.status_code, 302)

    def test_superuser_access(self):
        """Superuser obtient 200"""
        self.client.login(username="superadmin", password="testpass123")
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirect(self):
        """Utilisateur non connecté est redirigé vers login"""
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("connexion", response.headers.get("Location"))

    def test_workshops_displayed_in_view(self):
        """Les ateliers du mois suivant sont affichés"""
        next_month = self._next_month_start()
        Workshop.objects.create(
            title="Atelier Newsletter",
            description="Description test",
            start_date=next_month.replace(day=10),
            start_time=time(14, 0),
            end_time=time(16, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.superuser,
        )
        self.client.login(username="superadmin", password="testpass123")
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atelier Newsletter")
        self.assertContains(response, "Description test")

    def test_copy_buttons_present(self):
        """Les boutons de copie sont présents dans le template"""
        next_month = self._next_month_start()
        Workshop.objects.create(
            title="Atelier Copie",
            description="Description copie",
            start_date=next_month.replace(day=15),
            start_time=time(14, 0),
            end_time=time(16, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.superuser,
        )
        self.client.login(username="superadmin", password="testpass123")
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertContains(response, "data-copy")
        self.assertContains(response, "Copier")
        self.assertContains(response, "Tout copier")

    def test_empty_state_message(self):
        """Message approprié quand aucun atelier newsletter"""
        self.client.login(username="superadmin", password="testpass123")
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "aucun atelier")

    def test_newsletter_true_displayed(self):
        """Seuls les ateliers newsletter=True sont affichés"""
        next_month = self._next_month_start()
        Workshop.objects.create(
            title="Visible",
            description="Desc",
            start_date=next_month.replace(day=5),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=True,
            created_by=self.superuser,
        )
        Workshop.objects.create(
            title="Caché",
            description="Desc",
            start_date=next_month.replace(day=10),
            start_time=time(10, 0),
            end_time=time(12, 0),
            location=self.location,
            max_participants=10,
            newsletter=False,
            created_by=self.superuser,
        )
        self.client.login(username="superadmin", password="testpass123")
        response = self.client.get(reverse("library_workshops:newsletter"))
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Caché")
