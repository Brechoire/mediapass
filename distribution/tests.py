from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import CampagneDistribution, Commune, Distribution, Lieu


class CommuneModelTests(TestCase):
    def setUp(self):
        self.commune = Commune.objects.create(name="Testville")

    def test_commune_creation(self):
        self.assertEqual(self.commune.name, "Testville")
        self.assertEqual(str(self.commune), "Testville")

    def test_commune_unique_name(self):
        with self.assertRaises(Exception):
            Commune.objects.create(name="Testville")


class LieuModelTests(TestCase):
    def setUp(self):
        self.commune = Commune.objects.create(name="Testville")
        self.lieu = Lieu.objects.create(
            commune=self.commune,
            name="M\u00e9diath\u00e8que Centrale",
        )

    def test_lieu_creation(self):
        self.assertEqual(self.lieu.name, "M\u00e9diath\u00e8que Centrale")
        self.assertTrue(self.lieu.is_active)
        self.assertEqual(self.lieu.commune, self.commune)

    def test_lieu_unique_together(self):
        with self.assertRaises(Exception):
            Lieu.objects.create(
                commune=self.commune,
                name="M\u00e9diath\u00e8que Centrale",
            )


class CampagneDistributionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.commune = Commune.objects.create(name="Testville")
        self.lieu = Lieu.objects.create(
            commune=self.commune, name="M\u00e9diath\u00e8que"
        )
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne test",
            created_by=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

    def test_progression_zero_without_distributions(self):
        self.assertEqual(self.campagne.progression, 0)

    def test_progression_with_distributions(self):
        autre_lieu = Lieu.objects.create(
            commune=self.commune, name="Autre lieu"
        )
        Distribution.objects.create(
            campagne=self.campagne,
            lieu=self.lieu,
            is_distributed=True,
        )
        Distribution.objects.create(
            campagne=self.campagne,
            lieu=autre_lieu,
            is_distributed=False,
        )
        self.assertEqual(self.campagne.progression, 50)


class DistributionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.commune = Commune.objects.create(name="Testville")
        self.lieu = Lieu.objects.create(
            commune=self.commune, name="M\u00e9diath\u00e8que"
        )
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne test",
            created_by=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.distribution = Distribution.objects.create(
            campagne=self.campagne,
            lieu=self.lieu,
        )

    def test_auto_set_distributed_at(self):
        self.distribution.is_distributed = True
        self.distribution.save()
        self.assertIsNotNone(self.distribution.distributed_at)


class DistributionAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="normaluser", password="testpass123"
        )
        self.admin = User.objects.create_superuser(
            username="superadmin", password="admin123"
        )

    def test_index_redirects_anonymous(self):
        response = self.client.get(reverse("distribution:index"))
        self.assertNotEqual(response.status_code, 200)

    def test_index_normal_user_denied(self):
        self.client.login(username="normaluser", password="testpass123")
        response = self.client.get(reverse("distribution:index"))
        self.assertEqual(response.status_code, 302)

    def test_index_superuser_allowed(self):
        self.client.login(username="superadmin", password="admin123")
        response = self.client.get(reverse("distribution:index"))
        self.assertEqual(response.status_code, 200)

    def test_access_denied_view(self):
        from distribution.views import access_denied
        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.admin
        response = access_denied(request)
        self.assertIsNotNone(response)


class DistributionCRUDTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.commune = Commune.objects.create(name="Testville")

    def test_commune_create(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("distribution:commune_create"))
        self.assertEqual(response.status_code, 200)

    def test_campagne_list(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("distribution:campagne_list"))
        self.assertEqual(response.status_code, 200)
