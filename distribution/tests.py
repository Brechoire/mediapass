from datetime import date, timedelta
import html

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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

    def test_effective_status_active_before_end_date(self):
        self.campagne.end_date = timezone.localdate() + timedelta(days=1)
        self.assertEqual(self.campagne.effective_status, 'active')

    def test_effective_status_completed_after_end_date(self):
        self.campagne.end_date = timezone.localdate() - timedelta(days=1)
        self.assertEqual(self.campagne.effective_status, 'completed')

    def test_effective_status_untouched_for_other_statuses(self):
        self.campagne.end_date = timezone.localdate() - timedelta(days=10)
        self.campagne.status = 'cancelled'
        self.assertEqual(self.campagne.effective_status, 'cancelled')
        self.campagne.status = 'completed'
        self.assertEqual(self.campagne.effective_status, 'completed')


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


class LieuViewsTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.normal_user = User.objects.create_user(
            username="normal", password="testpass123"
        )
        self.commune = Commune.objects.create(name="Testville")
        self.lieu = Lieu.objects.create(
            commune=self.commune, name="M\u00e9diath\u00e8que"
        )

    def test_edit_modal_requires_login(self):
        url = reverse(
            "distribution:lieu_edit_modal",
            args=[self.commune.pk, self.lieu.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_edit_modal_denied_for_normal_user(self):
        url = reverse(
            "distribution:lieu_edit_modal",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="normal", password="testpass123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 403)

    def test_edit_modal_superuser_ok(self):
        url = reverse(
            "distribution:lieu_edit_modal",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="admin", password="admin123")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Modifier le lieu", response.content.decode())
        self.assertIn(self.lieu.name, response.content.decode())

    def test_update_success(self):
        url = reverse(
            "distribution:lieu_update",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="admin", password="admin123")
        response = self.client.post(
            url,
            {
                "name": "Biblioth\u00e8que du Centre",
                "description": "Nouveau lieu",
                "is_active": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["lieu_id"], self.lieu.pk)
        self.assertIn("lieu-card", data["card_html"])
        self.lieu.refresh_from_db()
        self.assertEqual(self.lieu.name, "Biblioth\u00e8que du Centre")
        self.assertEqual(self.lieu.description, "Nouveau lieu")
        self.assertFalse(self.lieu.is_active)

    def test_update_duplicate_name(self):
        Lieu.objects.create(commune=self.commune, name="Autre lieu")
        url = reverse(
            "distribution:lieu_update",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="admin", password="admin123")
        response = self.client.post(
            url,
            {"name": "Autre lieu", "description": "", "is_active": True},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("name", data["errors"])

    def test_update_denied_for_normal_user(self):
        url = reverse(
            "distribution:lieu_update",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="normal", password="testpass123")
        response = self.client.post(
            url,
            {"name": "Autre nom", "description": "", "is_active": True},
        )
        self.assertEqual(response.status_code, 403)

    def test_toggle(self):
        url = reverse(
            "distribution:lieu_toggle",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="admin", password="admin123")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.lieu.refresh_from_db()
        self.assertFalse(self.lieu.is_active)
        self.assertIn("Inactif", response.content.decode())
        self.assertIn("Activer", response.content.decode())

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.lieu.refresh_from_db()
        self.assertTrue(self.lieu.is_active)

    def test_toggle_denied_for_normal_user(self):
        url = reverse(
            "distribution:lieu_toggle",
            args=[self.commune.pk, self.lieu.pk],
        )
        self.client.login(username="normal", password="testpass123")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_commune_detail_shows_inactive_lieux(self):
        Lieu.objects.create(
            commune=self.commune, name="Ancien lieu", is_active=False
        )
        self.client.login(username="admin", password="admin123")
        response = self.client.get(
            reverse("distribution:commune_detail", args=[self.commune.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ancien lieu", response.content.decode())


class CampagneExpirationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.commune = Commune.objects.create(name="Testville")
        self.lieu = Lieu.objects.create(
            commune=self.commune, name="M\u00e9diath\u00e8que"
        )
        self.expired = CampagneDistribution.objects.create(
            name="Campagne expir\u00e9e",
            created_by=self.admin,
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() - timedelta(days=1),
            status="active",
        )
        self.future = CampagneDistribution.objects.create(
            name="Campagne future",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=10),
            status="active",
        )
        self.client.login(username="admin", password="admin123")

    def test_list_shows_expired_as_completed(self):
        response = self.client.get(reverse("distribution:campagne_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Termin\u00e9e", content)
        self.assertIn("En cours", content)

    def test_status_filter_active_excludes_expired(self):
        response = self.client.get(
            reverse("distribution:campagne_list"), {"status": "active"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Campagne future", content)
        self.assertNotIn("Campagne expir\u00e9e", content)

    def test_status_filter_completed_includes_expired(self):
        response = self.client.get(
            reverse("distribution:campagne_list"), {"status": "completed"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Campagne expir\u00e9e", content)
        self.assertNotIn("Campagne future", content)

    def test_statistics_counts_expired_as_completed(self):
        response = self.client.get(reverse("distribution:statistics"))
        self.assertEqual(response.status_code, 200)
        content = html.unescape(response.content.decode())
        self.assertIn("Campagne expir\u00e9e", content)
        self.assertIn("Termin\u00e9e", content)
