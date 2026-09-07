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
        self.soon = CampagneDistribution.objects.create(
            name="Campagne imminente",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=2),
            status="active",
        )
        self.client.login(username="admin", password="admin123")

    def test_list_sorted_by_nearest_end_date(self):
        response = self.client.get(reverse("distribution:campagne_list"))
        self.assertEqual(response.status_code, 200)
        names = [
            c.name for c in response.context["page_obj"].object_list
        ]
        self.assertEqual(
            names,
            ["Campagne imminente", "Campagne future", "Campagne expir\u00e9e"],
        )

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

    def test_detail_shows_expired_date_badge(self):
        response = self.client.get(
            reverse("distribution:campagne_detail", args=[self.expired.pk])
        )
        self.assertEqual(response.status_code, 200)
        content = html.unescape(response.content.decode())
        self.assertIn("Date d\u00e9pass\u00e9e", content)

    def test_statistics_shows_drafts_and_cancelled_counts(self):
        today = timezone.localdate()
        CampagneDistribution.objects.create(
            name="Brouillon",
            created_by=self.admin,
            start_date=today,
            end_date=today + timedelta(days=5),
            status="draft",
        )
        CampagneDistribution.objects.create(
            name="Annul\u00e9e",
            created_by=self.admin,
            start_date=today,
            end_date=today + timedelta(days=5),
            status="cancelled",
        )
        response = self.client.get(reverse("distribution:statistics"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["campagnes_drafts"], 1)
        self.assertEqual(response.context["campagnes_cancelled"], 1)
        content = html.unescape(response.content.decode())
        self.assertIn("Annul\u00e9es", content)

    def test_statistics_kpi_links(self):
        response = self.client.get(reverse("distribution:statistics"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("campagnes/?status=active", content)
        self.assertIn("campagnes/?status=completed", content)
        self.assertIn(reverse("distribution:commune_list"), content)

    def test_statistics_recent_ordered_by_end_date(self):
        response = self.client.get(reverse("distribution:statistics"))
        self.assertEqual(response.status_code, 200)
        names = [
            c.name for c in response.context["campagnes_recentes"]
        ]
        self.assertEqual(
            names,
            ["Campagne imminente", "Campagne future", "Campagne expir\u00e9e"],
        )


class CampagneProgressionBarTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.commune = Commune.objects.create(name="Testville")
        self.lieu1 = Lieu.objects.create(commune=self.commune, name="Lieu 1")
        self.lieu2 = Lieu.objects.create(commune=self.commune, name="Lieu 2")
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne barre",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=10),
            status="active",
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=self.lieu1, is_distributed=True
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=self.lieu2, is_distributed=False
        )
        self.client.login(username="admin", password="admin123")

    def test_detail_bar_uses_valid_width(self):
        response = self.client.get(
            reverse("distribution:campagne_detail", args=[self.campagne.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'style="width: 50%"', response.content.decode()
        )

    def test_list_bar_uses_valid_width(self):
        response = self.client.get(reverse("distribution:campagne_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'style="width: 50%"', response.content.decode()
        )

    def test_bar_zero_width_when_no_distributions(self):
        autre = CampagneDistribution.objects.create(
            name="Campagne vide",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=5),
            status="active",
        )
        response = self.client.get(
            reverse("distribution:campagne_detail", args=[autre.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'style="width: 0%"', response.content.decode()
        )


class BulkUpdateDistributionsTests(TestCase):
    """Non-régression P1 : 1 requête bulk au lieu de N requêtes unitaires."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.normal = User.objects.create_user(
            username="normal", password="testpass123"
        )
        self.commune = Commune.objects.create(name="Testville")
        self.lieux = [
            Lieu.objects.create(commune=self.commune, name=f"Lieu {i}")
            for i in range(3)
        ]
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne bulk",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=10),
            status="active",
        )
        self.distributions = [
            Distribution.objects.create(campagne=self.campagne, lieu=lieu)
            for lieu in self.lieux
        ]
        self.url = reverse(
            "distribution:bulk_update_distributions", args=[self.campagne.pk]
        )

    def _post(self, ids, action="validate"):
        import json

        return self.client.post(
            self.url,
            data=json.dumps({"ids": ids, "action": action}),
            content_type="application/json",
        )

    def test_denied_for_normal_user(self):
        self.client.login(username="normal", password="testpass123")
        response = self._post([self.distributions[0].pk])
        self.assertEqual(response.status_code, 403)

    def test_bulk_validate_sets_date_and_author(self):
        self.client.login(username="admin", password="admin123")
        ids = [d.pk for d in self.distributions[:2]]
        with self.assertNumQueries(10):
            # Détail : session + user + campagne SELECT + 2 UPDATE ciblés
            # + aggregate progression + savepoint/release + middleware
            # analytics (SELECT anti-doublon + INSERT). Le cœur bulk reste
            # 1 SELECT + 2 UPDATE + 1 aggregate contre N x 3 en fan-out.
            response = self._post(ids, action="validate")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["updated_count"], 2)
        for pk in ids:
            d = Distribution.objects.get(pk=pk)
            self.assertTrue(d.is_distributed)
            self.assertEqual(d.distributed_by, self.admin)
            self.assertIsNotNone(d.distributed_at)
        untouched = Distribution.objects.get(pk=self.distributions[2].pk)
        self.assertFalse(untouched.is_distributed)

    def test_bulk_validate_preserves_existing_date(self):
        old = self.distributions[0]
        old.is_distributed = True
        old.distributed_by = self.admin
        old.save()
        old.refresh_from_db()
        kept = old.distributed_at
        self.client.login(username="admin", password="admin123")
        response = self._post([old.pk], action="validate")
        self.assertEqual(response.status_code, 200)
        old.refresh_from_db()
        self.assertEqual(old.distributed_at, kept)

    def test_bulk_deselect_clears_date_and_author(self):
        target = self.distributions[0]
        target.is_distributed = True
        target.distributed_by = self.admin
        target.save()
        self.client.login(username="admin", password="admin123")
        response = self._post([target.pk], action="deselect")
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertFalse(target.is_distributed)
        self.assertIsNone(target.distributed_by)
        self.assertIsNone(target.distributed_at)

    def test_bulk_scoped_to_campagne(self):
        autre = CampagneDistribution.objects.create(
            name="Autre campagne",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=5),
            status="active",
        )
        intrus = Distribution.objects.create(
            campagne=autre, lieu=self.lieux[0]
        )
        self.client.login(username="admin", password="admin123")
        response = self._post(
            [self.distributions[0].pk, intrus.pk], action="validate"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated_count"], 1)
        intrus.refresh_from_db()
        self.assertFalse(intrus.is_distributed)

    def test_bulk_invalid_payload(self):
        self.client.login(username="admin", password="admin123")
        self.assertEqual(self._post([], action="validate").status_code, 400)
        self.assertEqual(
            self._post([self.distributions[0].pk], action="nope").status_code,
            400,
        )
