from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Kakemono, KakemonoReservation


class KakemonoModelTests(TestCase):
    def setUp(self):
        self.kakemono = Kakemono.objects.create(
            title="Test Kakemono",
            description="Description test",
            is_available=True,
        )

    def test_kakemono_creation(self):
        self.assertEqual(self.kakemono.title, "Test Kakemono")
        self.assertTrue(self.kakemono.is_available)
        self.assertEqual(str(self.kakemono), "Test Kakemono")

    def test_is_reserved(self):
        future = timezone.now().date() + timedelta(days=10)
        later = future + timedelta(days=5)
        self.assertFalse(self.kakemono.is_reserved(future, later))

        KakemonoReservation.objects.create(
            first_name="Jean",
            last_name="Dupont",
            start_date=future,
            end_date=later,
            status="confirmed",
        ).kakemonos.add(self.kakemono)

        self.assertTrue(self.kakemono.is_reserved(future, later))

    def test_is_reserved_pending_not_counted(self):
        future = timezone.now().date() + timedelta(days=10)
        later = future + timedelta(days=5)
        KakemonoReservation.objects.create(
            first_name="Jean",
            last_name="Dupont",
            start_date=future,
            end_date=later,
            status="pending",
        ).kakemonos.add(self.kakemono)

        self.assertFalse(self.kakemono.is_reserved(future, later))


class KakemonoReservationModelTests(TestCase):
    def setUp(self):
        self.kakemono = Kakemono.objects.create(title="Test Kakemono")

    def test_reservation_creation(self):
        future = timezone.now().date() + timedelta(days=5)
        later = future + timedelta(days=3)
        reservation = KakemonoReservation.objects.create(
            first_name="Marie",
            last_name="Martin",
            start_date=future,
            end_date=later,
            status="confirmed",
        )
        reservation.kakemonos.add(self.kakemono)
        self.assertEqual(reservation.first_name, "Marie")
        self.assertEqual(reservation.status, "confirmed")
        self.assertIn("Marie", str(reservation))

    def test_reservation_status_choices(self):
        future = timezone.now().date() + timedelta(days=5)
        later = future + timedelta(days=3)
        for status_value in ["pending", "confirmed", "cancelled"]:
            reservation = KakemonoReservation.objects.create(
                first_name="Test",
                last_name="User",
                start_date=future,
                end_date=later,
                status=status_value,
            )
            self.assertEqual(reservation.status, status_value)


class KakemonoListViewTests(TestCase):
    def setUp(self):
        for i in range(3):
            Kakemono.objects.create(title=f"Kakemono {i}")

    def test_list_all_kakemonos(self):
        response = self.client.get(reverse("kakemono:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kakemono 0")

    def test_detail_view(self):
        kakemono = Kakemono.objects.first()
        response = self.client.get(
            reverse("kakemono:detail", args=[kakemono.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, kakemono.title)


class KakemonoCRUDViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", password="admin123", email="admin@test.com"
        )
        self.kakemono = Kakemono.objects.create(title="Kakemono test")

    def test_create_view_requires_staff(self):
        response = self.client.get(reverse("kakemono:create"))
        self.assertNotEqual(response.status_code, 200)

    def test_create_view_staff(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("kakemono:create"))
        self.assertEqual(response.status_code, 200)

    def test_update_view_staff(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(
            reverse("kakemono:update", args=[self.kakemono.pk])
        )
        self.assertEqual(response.status_code, 200)


class KakemonoReservationViewTests(TestCase):
    def setUp(self):
        self.kakemono = Kakemono.objects.create(title="Test Kakemono")
        future = timezone.now().date() + timedelta(days=10)
        later = future + timedelta(days=5)
        self.reservation = KakemonoReservation.objects.create(
            first_name="Jean",
            last_name="Dupont",
            start_date=future,
            end_date=later,
            status="confirmed",
        )
        self.reservation.kakemonos.add(self.kakemono)

    def test_reservation_create_get(self):
        response = self.client.get(reverse("kakemono:reservation-create"))
        self.assertEqual(response.status_code, 200)

    def test_reservation_list(self):
        response = self.client.get(reverse("kakemono:reservation-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dupont")

    def test_reservation_detail(self):
        response = self.client.get(
            reverse("kakemono:reservation-detail", args=[self.reservation.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dupont")

    def test_reservation_list_requires_no_auth(self):
        response = self.client.get(reverse("kakemono:reservation-list"))
        self.assertEqual(response.status_code, 200)


class KakemonoAvailabilityAPITests(TestCase):
    def setUp(self):
        self.kakemono = Kakemono.objects.create(title="Test Kakemono")

    def test_check_availability_missing_params(self):
        self.client.login(username="testuser", password="testpass")
        User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse("kakemono:check_availability"))
        self.assertEqual(response.status_code, 400)

    def test_check_availability_requires_login(self):
        response = self.client.get(reverse("kakemono:check_availability"))
        self.assertNotEqual(response.status_code, 200)
