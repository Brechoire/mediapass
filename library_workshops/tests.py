from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db.models import Count, Q
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Workshop, WorkshopParticipant
from .forms import WorkshopForm, QuickLocationForm
from visitor_tracking.models import Location as VisitorLocation


class WorkshopModelTest(TestCase):
    """Tests pour le modèle Workshop"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque",
            icon="bx-building",
            color="#4F46E5"
        )

        self.workshop = Workshop.objects.create(
            title="Test Workshop",
            description="Description de test",
            start_date="2024-12-25",
            start_time="14:00",
            end_time="16:00",
            location=self.location,
            max_participants=10,
            created_by=self.user
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
            status='confirmed'
        )
        WorkshopParticipant.objects.create(
            workshop=self.workshop,
            first_name="Jane",
            last_name="Smith",
            age=30,
            status='waiting'
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
            created_by=self.user
        )
        self.assertIsNone(workshop2.location)

    def test_model_indexes(self):
        expected_indexes = {
            'idx_workshop_start',
            'idx_participant_ws_status',
        }
        db_indexes = set()
        for index in Workshop._meta.indexes:
            db_indexes.add(index.name)
        for index in WorkshopParticipant._meta.indexes:
            db_indexes.add(index.name)
        for expected in expected_indexes:
            self.assertIn(expected, db_indexes,
                         f"L'index {expected} est manquant")

    def test_start_date_db_index(self):
        self.assertTrue(Workshop._meta.get_field('start_date').db_index)

    def test_end_date_db_index(self):
        self.assertTrue(Workshop._meta.get_field('end_date').db_index)

    def test_status_db_index(self):
        self.assertTrue(WorkshopParticipant._meta.get_field('status').db_index)


class WorkshopFormTest(TestCase):
    """Tests pour le formulaire WorkshopForm"""

    def setUp(self):
        self.location = VisitorLocation.objects.create(
            name="Médiathèque",
            icon="bx-building",
            color="#4F46E5"
        )

    def test_form_valid_tout_public(self):
        form_data = {
            'title': 'Test Workshop',
            'description': 'Description de test',
            'start_date': '2024-12-25',
            'start_time': '14:00',
            'end_time': '16:00',
            'location': self.location.pk,
            'max_participants': 10,
            'is_all_ages': True,
            'newsletter': True,
            'is_class_welcome': False,
            'is_single_day': True
        }
        form = WorkshopForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_age_range(self):
        form_data = {
            'title': 'Test Workshop',
            'description': 'Description de test',
            'start_date': '2024-12-25',
            'start_time': '14:00',
            'end_time': '16:00',
            'location': self.location.pk,
            'max_participants': 10,
            'is_all_ages': False,
            'min_age': 7,
            'max_age': 12,
            'newsletter': True,
            'is_class_welcome': False,
            'is_single_day': True
        }
        form = WorkshopForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_age_range(self):
        form_data = {
            'title': 'Test Workshop',
            'description': 'Description de test',
            'start_date': '2024-12-25',
            'start_time': '14:00',
            'end_time': '16:00',
            'location': self.location.pk,
            'max_participants': 10,
            'is_all_ages': False,
            'min_age': 15,
            'max_age': 10,
            'newsletter': True,
            'is_class_welcome': False,
            'is_single_day': True
        }
        form = WorkshopForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "L'âge minimum ne peut pas être supérieur à l'âge maximum.",
            form.non_field_errors()
        )

    def test_form_invalid_time_range(self):
        form_data = {
            'title': 'Test Workshop',
            'description': 'Description de test',
            'start_date': '2024-12-25',
            'start_time': '16:00',
            'end_time': '14:00',
            'location': self.location.pk,
            'max_participants': 10,
            'is_all_ages': True,
            'newsletter': True,
            'is_class_welcome': False,
            'is_single_day': True
        }
        form = WorkshopForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "L'heure de fin doit être postérieure à l'heure de début.",
            form.non_field_errors()
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
        active_locations = form.fields['location'].queryset
        self.assertEqual(active_locations.count(), 2)
        self.assertNotIn("Ancien lieu", [loc.name for loc in active_locations])

    def test_form_location_empty_label(self):
        """Vérifie qu'il y a un empty_label"""
        form = WorkshopForm()
        self.assertEqual(form.fields['location'].empty_label,
                         "Sélectionnez un lieu...")


class QuickLocationFormTest(TestCase):
    """Tests pour le formulaire QuickLocationForm"""

    def test_form_valid(self):
        form = QuickLocationForm(data={
            'name': 'Nouveau lieu test',
            'icon': 'bx-building',
            'color': '#4F46E5'
        })
        self.assertTrue(form.is_valid())

    def test_form_invalid_empty_name(self):
        form = QuickLocationForm(data={
            'name': '',
            'icon': 'bx-building',
            'color': '#4F46E5'
        })
        self.assertFalse(form.is_valid())


class WorkshopViewsTest(TestCase):
    """Tests pour les vues"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque",
            icon="bx-building",
            color="#4F46E5"
        )
        self.mediatheque_group = Group.objects.create(name='mediatheque')
        self.user.groups.add(self.mediatheque_group)

    def test_index_view_authenticated_mediatheque(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('library_workshops:index'))
        self.assertEqual(response.status_code, 200)

    def test_index_view_authenticated_not_mediatheque(self):
        self.user.groups.remove(self.mediatheque_group)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('library_workshops:index'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers.get('Location'),
            reverse('home')
        )

    def test_index_view_not_authenticated(self):
        response = self.client.get(reverse('library_workshops:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('connexion', response.headers.get('Location'))

    def test_create_workshop_view_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('library_workshops:create_workshop'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Créer un nouvel atelier')

    def test_create_workshop_view_post_valid(self):
        self.client.login(username='testuser', password='testpass123')
        form_data = {
            'title': 'Test Workshop',
            'description': 'Description de test',
            'start_date': '2024-12-25',
            'start_time': '14:00',
            'end_time': '16:00',
            'location': self.location.pk,
            'max_participants': 10,
            'is_all_ages': True,
            'newsletter': True,
            'is_class_welcome': False,
            'is_single_day': True
        }
        response = self.client.post(
            reverse('library_workshops:create_workshop'), form_data
        )
        self.assertRedirects(response, reverse('library_workshops:index'))
        workshop = Workshop.objects.get(title='Test Workshop')
        self.assertEqual(workshop.created_by, self.user)
        self.assertEqual(workshop.location, self.location)

    def test_access_denied_view(self):
        response = self.client.get(reverse('library_workshops:access_denied'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Accès Refusé', status_code=403)


class WorkshopOptimizationTest(TestCase):
    """Tests pour les optimisations SQL et le N+1"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.group = Group.objects.create(name='mediatheque')
        self.user.groups.add(self.group)
        self.client.login(username='testuser', password='testpass123')
        self.location = VisitorLocation.objects.create(
            name="Médiathèque",
            icon="bx-building",
            color="#4F46E5"
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
                created_by=self.user
            )
            for j in range(3):
                WorkshopParticipant.objects.create(
                    workshop=workshop,
                    first_name=f"User{j}",
                    last_name=f"Test{i}",
                    age=20 + j,
                    status='confirmed' if j < 2 else 'waiting'
                )

    def test_index_view_annotates_participant_counts(self):
        """Vérifie que la vue index utilise des annotations pour éviter N+1"""
        response = self.client.get(reverse('library_workshops:index'))
        self.assertEqual(response.status_code, 200)

        workshops = response.context['workshops']
        for w in workshops:
            self.assertTrue(hasattr(w, 'confirmed_count'),
                           "L'annotation confirmed_count est manquante")
            self.assertTrue(hasattr(w, 'waiting_count'),
                           "L'annotation waiting_count est manquante")

    def test_annotated_counts_match_property(self):
        """Vérifie que les annotations correspondent aux propriétés du modèle"""
        response = self.client.get(reverse('library_workshops:index'))
        workshops = response.context['workshops']
        for w in workshops:
            self.assertEqual(
                w.confirmed_count,
                WorkshopParticipant.objects.filter(
                    workshop=w, status='confirmed'
                ).count()
            )

    def test_index_select_related_location(self):
        """Vérifie que la vue index utilise select_related pour éviter N+1"""
        response = self.client.get(reverse('library_workshops:index'))
        workshops = response.context['workshops']
        for w in workshops:
            with self.assertNumQueries(0):
                name = w.location.name


class LocationHTMXTest(TestCase):
    """Tests pour les endpoints HTMX de création de lieu"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.group = Group.objects.create(name='mediatheque')
        self.user.groups.add(self.group)
        self.client.login(username='testuser', password='testpass123')

    def test_create_location_modal_view(self):
        """Vérifie que le modal HTMX est accessible"""
        response = self.client.get(
            reverse('library_workshops:create_location_modal')
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('html', data)
        self.assertIn('Nouveau lieu', data['html'])

    def test_create_location_valid(self):
        """Vérifie la création d'un lieu via HTMX"""
        response = self.client.post(
            reverse('library_workshops:create_location'),
            {'name': 'Test Location', 'icon': 'bx-building', 'color': '#4F46E5'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['location_name'], 'Test Location')
        self.assertTrue(VisitorLocation.objects.filter(name='Test Location').exists())

    def test_create_location_duplicate(self):
        """Vérifie que les doublons sont rejetés"""
        VisitorLocation.objects.create(
            name="Doublon", icon="bx-building", color="#4F46E5", user=self.user
        )
        response = self.client.post(
            reverse('library_workshops:create_location'),
            {'name': 'Doublon', 'icon': 'bx-building', 'color': '#4F46E5'}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)

    def test_create_location_invalid(self):
        """Vérifie que les données invalides sont rejetées"""
        response = self.client.post(
            reverse('library_workshops:create_location'),
            {'name': '', 'icon': 'bx-building', 'color': '#4F46E5'}
        )
        self.assertEqual(response.status_code, 400)

    def test_create_location_not_authenticated(self):
        """Vérifie que l'authentification est requise (redirection vers login)"""
        self.client.logout()
        response = self.client.post(
            reverse('library_workshops:create_location'),
            {'name': 'Test', 'icon': 'bx-building', 'color': '#4F46E5'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('connexion', response.headers.get('Location'))

    def test_create_location_get_not_allowed(self):
        """Vérifie que GET sur create_location renvoie 405"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('library_workshops:create_location')
        )
        self.assertEqual(response.status_code, 405)


class WorkshopParticipantTest(TestCase):
    """Tests pour le modèle WorkshopParticipant"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.location = VisitorLocation.objects.create(
            name="Médiathèque",
            icon="bx-building",
            color="#4F46E5"
        )
        self.workshop = Workshop.objects.create(
            title="Test Workshop",
            description="Description de test",
            start_date="2024-12-25",
            start_time="14:00",
            end_time="16:00",
            location=self.location,
            max_participants=10,
            created_by=self.user
        )

    def test_participant_creation(self):
        participant = WorkshopParticipant.objects.create(
            workshop=self.workshop,
            first_name="John",
            last_name="Doe",
            age=25,
            email="john@example.com",
            status='confirmed',
            added_by=self.user
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
            status='confirmed'
        )
        self.assertEqual(participant.age_display, "1 an")
