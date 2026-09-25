"""Tests pour l'application shop.

Ce module contient les tests unitaires pour les modèles Category,
Product, Structure et Reservation de l'application shop.
"""

from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Product, Reservation, Structure


class CategoryTests(TestCase):
    """Tests pour le modèle Category."""

    def test_category_creation(self):
        """Crée une nouvelle catégorie."""
        category = Category.objects.create(name="Test Category")
        self.assertEqual(str(category), "Test Category")
        self.assertEqual(category.name, "Test Category")


class ProductTests(TestCase):
    """Tests pour le modèle Product."""

    def setUp(self):
        """Prépare l'environnement de test."""
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            quantity=10,
            description="Test Description",
            category=self.category,
            price=99.99,
            status=True,
        )

    def test_product_creation(self):
        """Crée un nouveau produit."""
        self.assertEqual(str(self.product), "Test Product")
        self.assertEqual(self.product.quantity, 10)
        self.assertEqual(self.product.price, 99.99)
        self.assertTrue(self.product.status)

    def test_product_availability(self):
        """Vérifie la disponibilité d'un produit pour des dates données."""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=2)

        # Test sans réservation
        self.assertTrue(self.product.is_available_for_dates(start_date, end_date))

        # Créer une structure pour la réservation
        structure = Structure.objects.create(
            name="Test Structure",
            address="123 Test St",
            city="Test City",
            email="test@test.com",
            zip_code="12345",
            country="Test Country",
        )

        # Créer une réservation approuvée
        Reservation.objects.create(
            product=self.product,
            start_date=start_date,
            end_date=end_date,
            structure=structure,
            quantity=1,
            is_approved=True,
        )

        # Test avec réservation existante
        self.assertFalse(self.product.is_available_for_dates(start_date, end_date))

    def test_reserve_and_cancel(self):
        """Test la réservation et l'annulation d'un produit."""
        initial_quantity = self.product.quantity

        # Test réservation
        self.product.reserve(2)
        self.assertEqual(self.product.quantity, initial_quantity - 2)

        # Test annulation
        self.product.cancel_reservation(2)
        self.assertEqual(self.product.quantity, initial_quantity)


class StructureTests(TestCase):
    """Tests pour le modèle Structure."""

    def test_structure_creation(self):
        """Crée une nouvelle structure."""
        structure = Structure.objects.create(
            name="Test Structure",
            address="123 Test St",
            city="Test City",
            email="test@test.com",
            zip_code="12345",
            country="Test Country",
            color="#FF0000",
            valid=True,
            is_registered=False,
        )
        self.assertEqual(str(structure), "Test Structure")
        self.assertEqual(structure.email, "test@test.com")
        self.assertTrue(structure.valid)
        self.assertFalse(structure.is_registered)


class ReservationTests(TestCase):
    """Tests pour le modèle Reservation."""

    def setUp(self):
        """Prépare l'environnement de test."""
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            quantity=10,
            description="Test Description",
            category=self.category,
            price=99.99,
            status=True,
        )
        self.structure = Structure.objects.create(
            name="Test Structure",
            address="123 Test St",
            city="Test City",
            email="test@test.com",
            zip_code="12345",
            country="Test Country",
        )
        self.reservation = Reservation.objects.create(
            product=self.product,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=2),
            structure=self.structure,
            quantity=2,
            deposit_time=datetime.now().time(),
            pickup_time=datetime.now().time(),
        )

    def test_reservation_creation(self):
        """Crée une nouvelle réservation."""
        self.assertEqual(self.reservation.quantity, 2)
        self.assertFalse(self.reservation.is_approved)

    def test_approve_and_cancel_reservation(self):
        """Test l'approbation et l'annulation d'une réservation."""
        initial_product_quantity = self.product.quantity

        # Test approbation
        self.reservation.approve_reservation()
        self.assertTrue(self.reservation.is_approved)
        self.assertEqual(
            self.product.quantity,
            initial_product_quantity - self.reservation.quantity,
        )

        # Test annulation
        self.reservation.cancel_reservation()
        self.assertFalse(self.reservation.is_approved)
        self.assertEqual(self.product.quantity, initial_product_quantity)


class ProductDetailViewTests(TestCase):
    """Tests pour la vue product_detail."""

    def setUp(self):
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            quantity=10,
            description="Test Description",
            category=self.category,
            price=99.99,
            status=True,
        )
        self.structure = Structure.objects.create(
            name="Test Structure",
            address="123 Test St",
            city="Test City",
            email="test@test.com",
            zip_code="12345",
            country="Test Country",
            is_registered=True,
        )
        self.other_structure = Structure.objects.create(
            name="Other Structure",
            address="456 Other St",
            city="Test City",
            email="other@test.com",
            zip_code="12345",
            country="Test Country",
            is_registered=False,
        )
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )

    def test_get_returns_200(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)

    def test_get_returns_404(self):
        response = self.client.get(reverse("product_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_product_name_in_page(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertContains(response, self.product.name)

    def test_category_name_in_page(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertContains(response, self.product.category.name)

    def test_staff_sees_admin_buttons(self):
        self.client.login(username="staff", password="pass")
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        content = response.content.decode()
        self.assertContains(response, "Modifier")
        self.assertContains(response, "Supprimer")

    def test_guest_does_not_see_admin_buttons(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertNotContains(response, "Modifier")
        self.assertNotContains(response, "Supprimer")

    def test_disabled_product_hides_form(self):
        self.product.status = False
        self.product.save()
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertNotContains(response, "Nouvelle réservation")

    def test_enabled_product_shows_form(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertContains(response, "Nouvelle réservation")

    def test_only_registered_structures_in_select(self):
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertContains(response, "Test Structure")
        self.assertNotContains(response, "Other Structure")

    def test_post_missing_fields_shows_errors(self):
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]), {}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ce champ est obligatoire")

    def test_post_quantity_exceeded_shows_error(self):
        tomorrow = date.today() + timedelta(days=1)
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": tomorrow.isoformat(),
                "end_date": (tomorrow + timedelta(days=2)).isoformat(),
                "structure": self.structure.pk,
                "quantity": 999,
                "deposit_time": "09:00",
                "pickup_time": "17:00",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "disponible")

    def test_structurte_starts_selected_on_error(self):
        tomorrow = date.today() + timedelta(days=1)
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": "",
                "end_date": (tomorrow + timedelta(days=2)).isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "09:00",
                "pickup_time": "17:00",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'value="{self.structure.pk}" selected',
            response.content.decode(),
        )

    def test_approved_reservations_appear_in_calendar(self):
        tomorrow = date.today() + timedelta(days=1)
        Reservation.objects.create(
            product=self.product,
            start_date=timezone.make_aware(
                datetime.combine(tomorrow, datetime.min.time()),
            ),
            end_date=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=3), datetime.min.time()),
            ),
            structure=self.structure,
            quantity=1,
            is_approved=True,
        )
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertContains(response, self.structure.name)

    def test_unapproved_reservations_hidden_from_calendar(self):
        tomorrow = date.today() + timedelta(days=1)
        Reservation.objects.create(
            product=self.product,
            start_date=timezone.make_aware(
                datetime.combine(tomorrow, datetime.min.time()),
            ),
            end_date=timezone.make_aware(
                datetime.combine(tomorrow + timedelta(days=3), datetime.min.time()),
            ),
            structure=self.structure,
            quantity=1,
            is_approved=False,
        )
        response = self.client.get(reverse("product_detail", args=[self.product.pk]))
        self.assertNotContains(response, f"'{self.structure.name}'")

    def _create_approved_reservation(
        self, start_date, end_date, deposit_time, pickup_time
    ):
        return Reservation.objects.create(
            product=self.product,
            start_date=timezone.make_aware(
                datetime.combine(start_date, datetime.min.time())
            ),
            end_date=timezone.make_aware(
                datetime.combine(end_date, datetime.min.time())
            ),
            structure=self.structure,
            quantity=1,
            deposit_time=deposit_time,
            pickup_time=pickup_time,
            is_approved=True,
        )

    def test_conflict_same_date_overlap(self):
        """Réservation existante: J+10 10h00 → J+13 10h00
        Nouvelle: J+12 09h00 → J+14 09h00 (OVERLAP)"""
        d = date.today() + timedelta(days=10)
        self._create_approved_reservation(d, d + timedelta(3), time(10, 0), time(10, 0))
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": (d + timedelta(2)).isoformat(),
                "end_date": (d + timedelta(4)).isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "09:00",
                "pickup_time": "09:00",
                "description": "",
            },
        )
        self.assertContains(response, "déjà réservé")

    def test_conflict_exact_same_slot(self):
        """Réservation existante: J+10 10h00 → J+13 10h00
        Nouvelle: J+10 10h00 → J+13 10h00 (OVERLAP exact)"""
        d = date.today() + timedelta(days=10)
        self._create_approved_reservation(d, d + timedelta(3), time(10, 0), time(10, 0))
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": d.isoformat(),
                "end_date": (d + timedelta(3)).isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "10:00",
                "pickup_time": "10:00",
                "description": "",
            },
        )
        self.assertContains(response, "déjà réservé")

    def test_no_conflict_after_return_time(self):
        """Réservation existante: J+10 10h00 → J+13 10h00
        Nouvelle: J+13 10h01 → J+15 10h00 (OK - juste après le retour)"""
        d = date.today() + timedelta(days=10)
        self._create_approved_reservation(d, d + timedelta(3), time(10, 0), time(10, 0))
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": (d + timedelta(3)).isoformat(),
                "end_date": (d + timedelta(5)).isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "10:01",
                "pickup_time": "10:00",
                "description": "",
            },
        )
        self.assertNotContains(response, "déjà réservé")

    def test_no_conflict_before_pickup_time(self):
        """Réservation existante: J+60 10h00 → J+63 10h00
        Nouvelle: J+58 08h00 → J+58 17h00 (OK - jour complètement avant)"""
        d = date.today() + timedelta(days=60)
        self._create_approved_reservation(d, d + timedelta(3), time(10, 0), time(10, 0))
        prev = d - timedelta(2)
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": prev.isoformat(),
                "end_date": prev.isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "08:00",
                "pickup_time": "17:00",
                "description": "",
            },
        )
        self.assertNotContains(response, "déjà réservé")

    def test_conflict_same_day_different_times(self):
        """Réservation existante: J+60 10h00 → J+62 12h00
        Nouvelle: J+61 09h00 → J+61 11h00 (OVERLAP multi-jour)"""
        d = date.today() + timedelta(days=60)
        self._create_approved_reservation(d, d + timedelta(2), time(10, 0), time(12, 0))
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": (d + timedelta(1)).isoformat(),
                "end_date": (d + timedelta(1)).isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "09:00",
                "pickup_time": "11:00",
                "description": "",
            },
        )
        self.assertContains(response, "déjà réservé")

    def test_no_conflict_same_day_adjacent_slots(self):
        """Réservation existante: J+10 10h00 → J+10 12h00
        Nouvelle: J+10 12h00 → J+10 14h00 (OK - créneaux adjacents)"""
        d = date.today() + timedelta(days=60)
        self._create_approved_reservation(d, d, time(10, 0), time(12, 0))
        response = self.client.post(
            reverse("product_detail", args=[self.product.pk]),
            {
                "start_date": d.isoformat(),
                "end_date": d.isoformat(),
                "structure": self.structure.pk,
                "quantity": 1,
                "deposit_time": "12:00",
                "pickup_time": "14:00",
                "description": "",
            },
        )
        self.assertNotContains(response, "déjà réservé")


class ProductListViewTests(TestCase):
    """Tests pour la vue product_list."""

    def setUp(self):
        self.category = Category.objects.create(name="Test Cat")
        Product.objects.create(
            name="Test Product",
            quantity=5,
            description="Test",
            category=self.category,
            price=99.99,
            status=True,
        )
        Product.objects.create(
            name="Disabled Product",
            quantity=0,
            description="Disabled",
            category=self.category,
            price=0,
            status=False,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def test_returns_200(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)

    def test_contains_product_names(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Test Product")
        self.assertContains(response, "Disabled Product")

    def test_contains_prices(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "99")

    def test_shows_status_badges(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "En rayon")
        self.assertContains(response, "Non disponible")

    def test_shows_category_name(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Test Cat")

    def test_shows_quantity(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "5")

    def test_empty_state_shown_when_no_products(self):
        self.client.login(username="admin", password="pass")
        Product.objects.all().delete()
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Aucun produit")

    def test_link_to_new_product(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Nouveau produit")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 302)

    def test_optimized_query_count(self):
        self.client.login(username="admin", password="pass")
        from django.db import connection

        connection.queries_log.clear()
        self.client.get(reverse("product_list"))
        self.assertLess(len(connection.queries), 8)

    def test_search_by_name(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get("/products/?q=Test")
        self.assertContains(response, "Test Product")

    def test_search_no_results(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get("/products/?q=ZZZZNOTFOUND")
        self.assertContains(response, "Aucun produit")

    def test_filter_by_category(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(f"/products/?cat={self.category.pk}")
        self.assertContains(response, "Test Product")

    def test_csv_export(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("product_list_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("Test Product", response.content.decode())

    def test_sort_by_price_asc(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get("/products/?sort=price&dir=asc")
        self.assertEqual(response.status_code, 200)

    def test_sort_by_price_desc(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get("/products/?sort=price&dir=desc")
        self.assertEqual(response.status_code, 200)

    def test_filter_and_search_combined(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(f"/products/?q=Test&cat={self.category.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")


class StructureListViewTests(TestCase):
    """Tests pour la vue structure_list."""

    def setUp(self):
        Structure.objects.create(
            name="Alpha Structure",
            address="1 Rue A",
            city="Paris",
            email="alpha@test.com",
            zip_code="75001",
            country="France",
            color="#FF0000",
            valid=True,
            is_registered=True,
        )
        Structure.objects.create(
            name="Beta Structure",
            address="2 Rue B",
            city="Lyon",
            email="beta@test.com",
            zip_code="69001",
            country="France",
            color="#00FF00",
            valid=False,
            is_registered=False,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("structure_list"))
        self.assertEqual(response.status_code, 200)

    def test_contains_names(self):
        self.login()
        response = self.client.get(reverse("structure_list"))
        self.assertContains(response, "Alpha Structure")
        self.assertContains(response, "Beta Structure")

    def test_shows_status_badges(self):
        self.login()
        response = self.client.get(reverse("structure_list"))
        self.assertContains(response, "Active")
        self.assertContains(response, "Inactive")

    def test_shows_city(self):
        self.login()
        response = self.client.get(reverse("structure_list"))
        self.assertContains(response, "Paris")
        self.assertContains(response, "Lyon")

    def test_search(self):
        self.login()
        response = self.client.get("/structures/?q=Alpha")
        self.assertContains(response, "Alpha Structure")
        self.assertNotContains(response, "Beta Structure")

    def test_search_no_results(self):
        self.login()
        response = self.client.get("/structures/?q=ZZZZZ")
        self.assertContains(response, "Aucune structure")

    def test_empty_state(self):
        self.login()
        Structure.objects.all().delete()
        response = self.client.get(reverse("structure_list"))
        self.assertContains(response, "Aucune structure")

    def test_csv_export(self):
        self.login()
        response = self.client.get("/structures/export/csv/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode()
        self.assertIn("Alpha Structure", content)
        self.assertIn("Beta Structure", content)

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("structure_list"))
        self.assertEqual(response.status_code, 302)

    def test_link_to_new_structure(self):
        self.login()
        response = self.client.get(reverse("structure_list"))
        self.assertContains(response, "Nouvelle structure")

    def test_shows_reservation_count(self):
        self.login()
        response = self.client.get(reverse("structure_list"))
        self.assertContains(response, "0")

    def test_sort_by_city(self):
        self.login()
        response = self.client.get("/structures/?sort=city&dir=asc")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paris")

    def test_sort_by_reservations(self):
        self.login()
        response = self.client.get("/structures/?sort=reservations&dir=asc")
        self.assertEqual(response.status_code, 200)


class StructureDetailViewTests(TestCase):
    """Tests pour la vue structure_detail."""

    def setUp(self):
        self.category = Category.objects.create(name="Test Cat")
        self.product = Product.objects.create(
            name="Test Product",
            quantity=5,
            category=self.category,
            price=99.99,
            status=True,
        )
        self.structure = Structure.objects.create(
            name="Test Structure",
            address="1 Rue",
            city="Paris",
            email="a@b.com",
            zip_code="75",
            country="FR",
            color="#FF0000",
            valid=True,
            is_registered=True,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_contains_name(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, "Test Structure")

    def test_contains_stats(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, "Réservations")
        self.assertContains(response, "0")

    def test_with_reservation_shows_product(self):
        from datetime import datetime
        from django.utils import timezone

        Reservation.objects.create(
            product=self.product,
            structure=self.structure,
            start_date=timezone.make_aware(datetime(2026, 6, 1)),
            end_date=timezone.make_aware(datetime(2026, 6, 5)),
            quantity=1,
            is_approved=True,
        )
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, "Test Product")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_year_filter(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk]) + "?year=2025"
        )
        self.assertEqual(response.status_code, 200)

    def test_returns_404(self):
        self.login()
        response = self.client.get(reverse("structure_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_shows_validity_badge(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, "Active")

    def test_stats_cards_are_links(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, reverse("reservation_list"))

    def test_shows_progress_bars(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, "rounded-full")

    def test_shows_top_workshops_empty_state(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk])
        )
        self.assertContains(response, "Aucun atelier")

    def test_year_filter_no_data(self):
        self.login()
        response = self.client.get(
            reverse("structure_detail", args=[self.structure.pk]) + "?year=1990"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0")


class StructureUpdateViewTests(TestCase):
    """Tests pour la vue structure_update."""

    def setUp(self):
        self.structure = Structure.objects.create(
            name="Test Structure",
            address="1 Rue",
            city="Paris",
            email="a@b.com",
            zip_code="75",
            country="FR",
            color="#FF0000",
            valid=True,
            is_registered=True,
        )
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_contains_name(self):
        self.login()
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertContains(response, "Test Structure")

    def test_contains_form_fields(self):
        self.login()
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertContains(response, "name")
        self.assertContains(response, "email")
        self.assertContains(response, "city")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_returns_404(self):
        self.login()
        response = self.client.get(reverse("structure_update", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_post_valid_updates_structure(self):
        self.login()
        response = self.client.post(
            reverse("structure_update", args=[self.structure.pk]),
            {
                "name": "Updated Name",
                "email": "updated@test.com",
                "address": "2 Rue",
                "city": "Lyon",
                "zip_code": "69",
                "country": "FR",
                "color": "#00FF00",
                "valid": True,
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("structure_list"))

        self.structure.refresh_from_db()
        self.assertEqual(self.structure.name, "Updated Name")

    def test_post_invalid_shows_errors(self):
        self.login()
        response = self.client.post(
            reverse("structure_update", args=[self.structure.pk]),
            {
                "name": "",
                "email": "bad-email",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obligatoire")

    def test_shows_validation_banner_if_unregistered(self):
        self.structure.is_registered = False
        self.structure.save()
        self.login()
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertContains(response, "attente de validation")

    def test_hides_validation_banner_if_registered(self):
        self.login()
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertNotContains(response, "attente de validation")

    def test_color_preview_styles(self):
        self.login()
        response = self.client.get(
            reverse("structure_update", args=[self.structure.pk])
        )
        self.assertContains(response, "color-preview")


class StructureCreateViewTests(TestCase):
    """Tests pour la vue structure_create."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("structure_create"))
        self.assertEqual(response.status_code, 200)

    def test_contains_form(self):
        self.login()
        response = self.client.get(reverse("structure_create"))
        self.assertContains(response, "Nouvelle structure")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("structure_create"))
        self.assertEqual(response.status_code, 302)

    def test_post_valid_creates_structure(self):
        self.login()
        response = self.client.post(
            reverse("structure_create"),
            {
                "name": "New Structure",
                "email": "new@test.com",
                "address": "1 Rue",
                "city": "Paris",
                "zip_code": "75",
                "country": "FR",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("structure_list"))

    def test_post_invalid_shows_errors(self):
        self.login()
        response = self.client.post(
            reverse("structure_create"),
            {
                "name": "",
                "email": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obligatoire")


class CategoryListViewTests(TestCase):
    """Tests pour la vue category_list."""

    def setUp(self):
        self.cat = Category.objects.create(name="Test Cat")
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("category_list"))
        self.assertEqual(response.status_code, 200)

    def test_contains_name(self):
        self.login()
        response = self.client.get(reverse("category_list"))
        self.assertContains(response, "Test Cat")

    def test_search(self):
        self.login()
        response = self.client.get("/categories/?q=Test")
        self.assertContains(response, "Test Cat")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("category_list"))
        self.assertEqual(response.status_code, 302)

    def test_empty_state(self):
        self.login()
        Category.objects.all().delete()
        response = self.client.get(reverse("category_list"))
        self.assertContains(response, "Aucune catégorie")


class CategoryCreateViewTests(TestCase):
    """Tests pour la vue category_create."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("category_create"))
        self.assertEqual(response.status_code, 200)

    def test_contains_form(self):
        self.login()
        response = self.client.get(reverse("category_create"))
        self.assertContains(response, "Ajouter")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("category_create"))
        self.assertEqual(response.status_code, 302)

    def test_post_valid_creates_category(self):
        self.login()
        response = self.client.post(
            reverse("category_create"), {"name": "New Cat"}, follow=True
        )
        self.assertRedirects(response, reverse("category_list"))

    def test_post_invalid_shows_errors(self):
        self.login()
        response = self.client.post(reverse("category_create"), {"name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obligatoire")


class StatisticsViewTests(TestCase):
    """Tests pour la vue statistics."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("statistics"))
        self.assertEqual(response.status_code, 200)

    def test_contains_title(self):
        self.login()
        response = self.client.get(reverse("statistics"))
        self.assertContains(response, "Statistiques")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("statistics"))
        self.assertEqual(response.status_code, 302)

    def test_year_filter(self):
        self.login()
        response = self.client.get("/Statistiques/?year=2025")
        self.assertEqual(response.status_code, 200)

    def test_invalid_year_falls_back_to_current_year(self):
        from datetime import datetime

        self.login()
        response = self.client.get("/Statistiques/?year=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_year"], datetime.now().year)

    def test_empty_year_still_renders(self):
        self.login()
        response = self.client.get(reverse("statistics") + "?year=1990")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune r")
        self.assertEqual(response.context["total_reservations"], 0)
        self.assertEqual(response.context["monthly_average"], 0.0)

    def test_counts_and_top_context(self):
        from django.utils import timezone

        category = Category.objects.create(name="Cat Stats")
        product = Product.objects.create(
            name="Produit L'Apostrophe",
            quantity=10,
            description="x",
            category=category,
            price=10,
            status=True,
        )
        structure = Structure.objects.create(
            name="Structure Top",
            address="1 rue",
            city="Ville",
            email="s@t.fr",
            zip_code="59",
            country="FR",
        )
        year = timezone.now().year
        Reservation.objects.create(
            product=product,
            start_date=timezone.make_aware(timezone.datetime(year, 3, 5)),
            end_date=timezone.make_aware(timezone.datetime(year, 3, 6)),
            structure=structure,
            quantity=1,
        )
        Reservation.objects.create(
            product=product,
            start_date=timezone.make_aware(timezone.datetime(year, 3, 12)),
            end_date=timezone.make_aware(timezone.datetime(year, 3, 13)),
            structure=structure,
            quantity=1,
        )
        self.login()
        response = self.client.get(reverse("statistics") + f"?year={year}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_reservations"], 2)
        self.assertEqual(response.context["monthly_average"], round(2 / 12, 1))
        self.assertEqual(response.context["reservations_by_month"][2], 2)
        self.assertEqual(response.context["monthly_max_index"], 2)
        self.assertEqual(response.context["top_structure"].name, "Structure Top")
        self.assertEqual(response.context["top_product"].name, "Produit L'Apostrophe")
        # escapejs : le template ne doit pas casser sur l'apostrophe
        self.assertContains(response, "Produit L")

    def _make_stats_setup(self, year):
        from django.utils import timezone

        category = Category.objects.create(name="Cat Phase A")
        product = Product.objects.create(
            name="Produit Phase A",
            quantity=50,
            description="x",
            category=category,
            price=10,
            status=True,
        )
        dormant = Product.objects.create(
            name="Produit Dormant",
            quantity=5,
            description="x",
            category=category,
            price=5,
            status=True,
        )
        structure = Structure.objects.create(
            name="Structure Phase A",
            address="1 rue",
            city="Ville",
            email="p@t.fr",
            zip_code="59",
            country="FR",
        )

        def make_resa(day, qty, **kwargs):
            return Reservation.objects.create(
                product=product,
                start_date=timezone.make_aware(timezone.datetime(year, 3, day)),
                end_date=timezone.make_aware(timezone.datetime(year, 3, day + 1)),
                structure=structure,
                quantity=qty,
                **kwargs,
            )

        make_resa(5, 2, is_approved=True)
        make_resa(6, 4)  # en attente
        make_resa(7, 1, is_rejected=True, disapproval_reason="unavailable")
        return year, dormant

    def test_funnel_counts_and_links(self):
        from django.utils import timezone

        year = timezone.now().year
        self._make_stats_setup(year)
        self.login()
        response = self.client.get(reverse("statistics") + f"?year={year}")
        funnel = response.context["funnel"]
        self.assertEqual(funnel["approved"], 1)
        self.assertEqual(funnel["pending"], 1)
        self.assertEqual(funnel["rejected"], 1)
        self.assertEqual(funnel["approval_rate"], round(1 / 3 * 100, 1))
        content = response.content.decode()
        self.assertIn("status=pending", content)
        self.assertIn("status=approved", content)
        self.assertIn("status=rejected", content)
        self.assertContains(response, "validation des demandes")

    def test_volumes_and_basket(self):
        from django.utils import timezone

        year = timezone.now().year
        self._make_stats_setup(year)
        self.login()
        response = self.client.get(reverse("statistics") + f"?year={year}")
        self.assertEqual(response.context["total_quantity"], 7)
        self.assertEqual(response.context["avg_basket"], round(7 / 3, 1))

    def test_categories_and_dormant(self):
        from django.utils import timezone

        year = timezone.now().year
        self._make_stats_setup(year)
        self.login()
        response = self.client.get(reverse("statistics") + f"?year={year}")
        chart_categories = response.context["chart_categories"]
        self.assertEqual(len(chart_categories), 1)
        self.assertEqual(chart_categories[0]["name"], "Cat Phase A")
        self.assertEqual(chart_categories[0]["total"], 3)
        self.assertEqual(chart_categories[0]["quantity"], 7)
        self.assertEqual(response.context["dormant_count"], 1)
        self.assertEqual(response.context["dormant_sample"][0].name, "Produit Dormant")
        self.assertContains(response, "jamais r")

    def test_duration_stats(self):
        from django.utils import timezone

        category = Category.objects.create(name="Cat Durées")
        product = Product.objects.create(
            name="Produit Durées",
            quantity=50,
            description="x",
            category=category,
            price=10,
            status=True,
        )
        structure = Structure.objects.create(
            name="Structure Durées",
            address="1 rue",
            city="Ville",
            email="d@t.fr",
            zip_code="59",
            country="FR",
        )
        year = timezone.now().year

        def make_resa(start_day, end_day):
            return Reservation.objects.create(
                product=product,
                start_date=timezone.make_aware(timezone.datetime(year, 4, start_day)),
                end_date=timezone.make_aware(timezone.datetime(year, 4, end_day)),
                structure=structure,
                quantity=1,
            )

        make_resa(1, 2)  # 1 jour
        make_resa(3, 6)  # 3 jours
        make_resa(10, 20)  # 10 jours
        self.login()
        response = self.client.get(reverse("statistics") + f"?year={year}")
        durations = response.context["duration_stats"]
        self.assertEqual(durations["median"], 3.0)
        self.assertEqual(durations["mean"], round(14 / 3, 1))
        self.assertEqual(durations["short_share"], round(2 / 3 * 100, 1))
        self.assertEqual(durations["long_share"], round(1 / 3 * 100, 1))
        self.assertContains(response, "diane")


class ReservationCalendarViewTests(TestCase):
    """Tests pour la vue reservation_calendar."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("reservation_calendar"))
        self.assertEqual(response.status_code, 200)

    def test_contains_title(self):
        self.login()
        response = self.client.get(reverse("reservation_calendar"))
        self.assertContains(response, "Calendrier")

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("reservation_calendar"))
        self.assertEqual(response.status_code, 302)

    def _noon(self):
        from django.utils import timezone

        return timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)

    def _make_calendar_setup(self, base):
        category = Category.objects.create(name="Cat Calendrier")
        product = Product.objects.create(
            name="Produit Calendrier",
            quantity=50,
            description="x",
            category=category,
            price=10,
            status=True,
        )
        structure_a = Structure.objects.create(
            name="Structure Cal A",
            address="1 rue",
            city="Ville",
            email="a@t.fr",
            zip_code="59",
            country="FR",
        )
        structure_b = Structure.objects.create(
            name="Structure Cal B",
            address="2 rue",
            city="Ville",
            email="b@t.fr",
            zip_code="59",
            country="FR",
        )
        # Départs dans la journée (base = midi figé, +1h reste le même jour)
        resa_a = Reservation.objects.create(
            product=product,
            start_date=base + timedelta(hours=1),
            end_date=base + timedelta(days=2),
            structure=structure_a,
            quantity=2,
            is_approved=True,
            deposit_time=time(9, 0),
        )
        Reservation.objects.create(
            product=product,
            start_date=base + timedelta(hours=1),
            end_date=base + timedelta(days=2),
            structure=structure_b,
            quantity=1,
            is_approved=True,
        )
        # Retour à venir dans 5 jours (structure A, approuvée)
        Reservation.objects.create(
            product=product,
            start_date=base - timedelta(days=2),
            end_date=base + timedelta(days=5),
            structure=structure_a,
            quantity=1,
            is_approved=True,
            pickup_time=time(17, 30),
        )
        return structure_a, structure_b, resa_a

    def _get_calendar(self, noon, **params):
        from unittest import mock

        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = reverse("reservation_calendar") + (f"?{query}" if query else "")
        with mock.patch("django.utils.timezone.now", return_value=noon):
            return self.client.get(url)

    def test_horizon_invalid_falls_back_to_15(self):
        self.login()
        response = self.client.get(reverse("reservation_calendar") + "?horizon=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["horizon"], 15)
        response = self.client.get(reverse("reservation_calendar") + "?horizon=7")
        self.assertEqual(response.context["horizon"], 7)

    def test_kpis_filtered_by_structure(self):
        noon = self._noon()
        structure_a, _structure_b, _resa_a = self._make_calendar_setup(noon)
        self.login()
        response = self._get_calendar(noon, structure=structure_a.pk)
        self.assertEqual(response.context["departures_today_count"], 1)
        self.assertEqual(len(response.context["returns_groups"]), 2)
        response_all = self._get_calendar(noon)
        self.assertEqual(response_all.context["departures_today_count"], 2)

    def test_grouped_lists_links_and_slots(self):
        noon = self._noon()
        _a, _b, resa_a = self._make_calendar_setup(noon)
        self.login()
        response = self._get_calendar(noon)
        groups = response.context["departures_groups"]
        self.assertTrue(len(groups) >= 1)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["units"], 3)
        self.assertContains(response, reverse("reservation_details", args=[resa_a.pk]))
        self.assertContains(response, "09:00")
        self.assertContains(response, "17:30")
        self.assertContains(response, "Aujourd'hui")


class ReservationListViewTests(TestCase):
    """Tests pour la vue reservation_list."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get(reverse("reservation_list"))
        self.assertEqual(response.status_code, 200)

    def test_contains_title(self):
        self.login()
        response = self.client.get(reverse("reservation_list"))
        self.assertContains(response, "Liste des réservations")

    def test_filter_year(self):
        self.login()
        response = self.client.get("/reservations/?year=2025")
        self.assertEqual(response.status_code, 200)

    def test_filter_status(self):
        self.login()
        response = self.client.get("/reservations/?status=approved")
        self.assertEqual(response.status_code, 200)

    def test_filter_structure(self):
        self.login()
        response = self.client.get("/reservations/?structure=1")
        self.assertEqual(response.status_code, 200)

    def test_redirects_when_not_logged_in(self):
        response = self.client.get(reverse("reservation_list"))
        self.assertEqual(response.status_code, 302)
