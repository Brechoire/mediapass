from datetime import date, timedelta
import html

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    CampagneDistribution, CampagneLieuExclusion, Commune, Distribution, Lieu
)


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
        with self.assertNumQueries(11):
            # Détail : session + user + campagne SELECT + 2 UPDATE ciblés
            # + aggregate progression (lieux + quantités) + totaux par
            # commune + savepoint/release + middleware analytics
            # (SELECT anti-doublon + INSERT). Le cœur bulk reste
            # 1 SELECT + 2 UPDATE + 2 aggregates contre N x 3 en fan-out.
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


class DistributionQuantiteModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.commune = Commune.objects.create(name="Anor")
        self.lieu = Lieu.objects.create(commune=self.commune, name="Le36")
        self.campagne1 = CampagneDistribution.objects.create(
            name="Campagne 01",
            created_by=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.campagne2 = CampagneDistribution.objects.create(
            name="Campagne 02",
            created_by=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

    def test_quantite_defaults_to_zero(self):
        dist = Distribution.objects.create(
            campagne=self.campagne1, lieu=self.lieu
        )
        self.assertEqual(dist.quantite, 0)

    def test_quantite_negative_rejected(self):
        from django.core.exceptions import ValidationError
        dist = Distribution(
            campagne=self.campagne1, lieu=self.lieu, quantite=-1
        )
        with self.assertRaises(ValidationError):
            dist.full_clean()

    def test_quantite_independent_per_campagne(self):
        Distribution.objects.create(
            campagne=self.campagne1, lieu=self.lieu, quantite=50
        )
        Distribution.objects.create(
            campagne=self.campagne2, lieu=self.lieu, quantite=20
        )
        self.assertEqual(
            Distribution.objects.get(
                campagne=self.campagne1, lieu=self.lieu
            ).quantite,
            50,
        )
        self.assertEqual(
            Distribution.objects.get(
                campagne=self.campagne2, lieu=self.lieu
            ).quantite,
            20,
        )

    def test_campagne_totaux_quantite(self):
        autre_lieu = Lieu.objects.create(
            commune=self.commune, name="Mairie"
        )
        Distribution.objects.create(
            campagne=self.campagne1, lieu=self.lieu,
            quantite=50, is_distributed=True,
        )
        Distribution.objects.create(
            campagne=self.campagne1, lieu=autre_lieu, quantite=20
        )
        self.campagne1.refresh_from_db()
        self.assertEqual(self.campagne1.total_quantite, 70)
        self.assertEqual(self.campagne1.quantite_distribuee, 50)
        self.assertEqual(self.campagne1.progression_quantite, 71.4)

    def test_progression_quantite_zero_total(self):
        self.assertEqual(self.campagne1.progression_quantite, 0)


class UpdateQuantiteViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.normal = User.objects.create_user(
            username="normal", password="testpass123"
        )
        self.commune = Commune.objects.create(name="Anor")
        self.lieu = Lieu.objects.create(commune=self.commune, name="Le36")
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne 01",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=10),
            status="active",
        )
        self.distribution = Distribution.objects.create(
            campagne=self.campagne, lieu=self.lieu
        )
        self.url = reverse(
            "distribution:update_distribution_quantite",
            args=[self.campagne.pk, self.distribution.pk],
        )

    def _post(self, payload):
        import json
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_denied_for_normal_user(self):
        self.client.login(username="normal", password="testpass123")
        self.assertEqual(
            self._post({"quantite": 50}).status_code, 403
        )

    def test_update_success_with_totals(self):
        self.client.login(username="admin", password="admin123")
        response = self._post({"quantite": 50})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["quantite"], 50)
        self.assertEqual(data["total_quantite"], 50)
        self.assertEqual(data["quantite_distribuee"], 0)
        self.assertEqual(data["commune_id"], self.commune.pk)
        self.assertEqual(data["commune_total_quantite"], 50)
        self.distribution.refresh_from_db()
        self.assertEqual(self.distribution.quantite, 50)

    def test_update_counts_distribuee_when_checked(self):
        self.distribution.is_distributed = True
        self.distribution.distributed_by = self.admin
        self.distribution.save()
        self.client.login(username="admin", password="admin123")
        data = self._post({"quantite": 70}).json()
        self.assertEqual(data["quantite_distribuee"], 70)
        self.assertEqual(data["commune_quantite_distribuee"], 70)

    def test_update_invalid_payload(self):
        self.client.login(username="admin", password="admin123")
        self.assertEqual(self._post({"quantite": -5}).status_code, 400)
        self.assertEqual(
            self._post({"quantite": "beaucoup"}).status_code, 400
        )
        self.assertEqual(self._post({}).status_code, 400)
        self.distribution.refresh_from_db()
        self.assertEqual(self.distribution.quantite, 0)

    def test_update_scoped_to_campagne(self):
        autre = CampagneDistribution.objects.create(
            name="Autre campagne",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=5),
            status="active",
        )
        bad_url = reverse(
            "distribution:update_distribution_quantite",
            args=[autre.pk, self.distribution.pk],
        )
        self.client.login(username="admin", password="admin123")
        import json
        response = self.client.post(
            bad_url,
            data=json.dumps({"quantite": 10}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


class BulkSetQuantitesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.normal = User.objects.create_user(
            username="normal", password="testpass123"
        )
        self.commune = Commune.objects.create(name="Anor")
        self.lieux = [
            Lieu.objects.create(commune=self.commune, name=f"Lieu {i}")
            for i in range(3)
        ]
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne 01",
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
            "distribution:bulk_set_quantites", args=[self.campagne.pk]
        )

    def _post(self, quantite, scope="all"):
        import json
        return self.client.post(
            self.url,
            data=json.dumps({"quantite": quantite, "scope": scope}),
            content_type="application/json",
        )

    def test_denied_for_normal_user(self):
        self.client.login(username="normal", password="testpass123")
        self.assertEqual(self._post(70).status_code, 403)

    def test_apply_all(self):
        self.client.login(username="admin", password="admin123")
        response = self._post(70, scope="all")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["updated_count"], 3)
        self.assertEqual(data["total_quantite"], 210)
        self.assertIn(str(self.commune.pk), data["communes_quantites"])
        for dist in self.distributions:
            dist.refresh_from_db()
            self.assertEqual(dist.quantite, 70)

    def test_apply_only_zero_preserves_filled(self):
        self.distributions[0].quantite = 50
        self.distributions[0].save(update_fields=["quantite"])
        self.client.login(username="admin", password="admin123")
        data = self._post(70, scope="only_zero").json()
        self.assertEqual(data["updated_count"], 2)
        self.assertEqual(data["total_quantite"], 190)
        self.distributions[0].refresh_from_db()
        self.assertEqual(self.distributions[0].quantite, 50)

    def test_invalid_payload(self):
        self.client.login(username="admin", password="admin123")
        self.assertEqual(self._post(-1).status_code, 400)
        self.assertEqual(self._post("x").status_code, 400)
        self.assertEqual(self._post(10, scope="nope").status_code, 400)

    def test_campagne_create_generates_zero_quantites(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.post(
            reverse("distribution:campagne_create"),
            {
                "name": "Nouvelle campagne",
                "status": "active",
                "start_date": timezone.localdate().isoformat(),
                "end_date": (
                    timezone.localdate() + timedelta(days=5)
                ).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        campagne = CampagneDistribution.objects.get(
            name="Nouvelle campagne"
        )
        self.assertTrue(campagne.distributions.exists())
        self.assertFalse(
            campagne.distributions.exclude(quantite=0).exists()
        )


class CampagneDetailQuantiteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.commune = Commune.objects.create(name="Anor")
        self.lieu = Lieu.objects.create(commune=self.commune, name="Le36")
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne 01",
            created_by=self.admin,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=10),
            status="active",
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=self.lieu, quantite=50
        )
        self.client.login(username="admin", password="admin123")

    def test_detail_shows_quantite_inputs_and_counters(self):
        response = self.client.get(
            reverse("distribution:campagne_detail", args=[self.campagne.pk])
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("quantite-input", content)
        self.assertIn("global-docs-counter", content)
        self.assertIn(f"commune-docs-{self.commune.pk}", content)
        self.assertIn("uniform-quantite", content)
        self.assertIn("0/50 docs", html.unescape(content))
        self.assertIn("0/50 documents", html.unescape(content))


class CampagneDeleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.normal = User.objects.create_user(
            username="normal", password="testpass123"
        )
        self.commune = Commune.objects.create(name="Anor")
        self.lieu = Lieu.objects.create(commune=self.commune, name="Le36")
        self.autre_lieu = Lieu.objects.create(
            commune=self.commune, name="Mairie"
        )
        today = timezone.localdate()
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne en double",
            created_by=self.admin,
            start_date=today,
            end_date=today + timedelta(days=10),
            status="active",
        )
        self.doublon = CampagneDistribution.objects.create(
            name="Campagne en double",
            created_by=self.admin,
            start_date=today,
            end_date=today + timedelta(days=10),
            status="active",
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=self.lieu,
            quantite=50, is_distributed=True,
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=self.autre_lieu, quantite=20
        )
        Distribution.objects.create(
            campagne=self.doublon, lieu=self.lieu, quantite=70
        )
        self.url = reverse(
            "distribution:campagne_delete", args=[self.campagne.pk]
        )

    def test_get_shows_confirmation_without_deleting(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = html.unescape(response.content.decode())
        self.assertIn("Supprimer la campagne", content)
        self.assertIn("2 lieu(x)", content)
        self.assertTrue(
            CampagneDistribution.objects.filter(pk=self.campagne.pk).exists()
        )

    def test_post_deletes_campagne_only(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, reverse("distribution:campagne_list"))
        self.assertFalse(
            CampagneDistribution.objects.filter(pk=self.campagne.pk).exists()
        )
        # Distributions de la campagne supprimée : parties.
        self.assertFalse(
            Distribution.objects.filter(campagne_id=self.campagne.pk).exists()
        )
        # Lieux, commune et campagne en double : intacts.
        self.assertTrue(Lieu.objects.filter(pk=self.lieu.pk).exists())
        self.assertTrue(Lieu.objects.filter(pk=self.autre_lieu.pk).exists())
        self.assertTrue(Commune.objects.filter(pk=self.commune.pk).exists())
        doublon_dist = Distribution.objects.get(
            campagne=self.doublon, lieu=self.lieu
        )
        self.assertEqual(doublon_dist.quantite, 70)
        self.assertFalse(doublon_dist.is_distributed)

    def test_delete_denied_for_normal_user(self):
        self.client.login(username="normal", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CampagneDistribution.objects.filter(pk=self.campagne.pk).exists()
        )

    def test_delete_requires_login(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)
        self.assertTrue(
            CampagneDistribution.objects.filter(pk=self.campagne.pk).exists()
        )

    def test_delete_unknown_campagne_404(self):
        self.client.login(username="admin", password="admin123")
        url = reverse("distribution:campagne_delete", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)


class RetirerLieuCampagneTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.normal = User.objects.create_user(
            username="normal", password="testpass123"
        )
        self.commune = Commune.objects.create(name="Anor")
        self.lieu = Lieu.objects.create(commune=self.commune, name="Le36")
        self.autre_lieu = Lieu.objects.create(
            commune=self.commune, name="Mairie"
        )
        today = timezone.localdate()
        self.campagne = CampagneDistribution.objects.create(
            name="Campagne 01",
            created_by=self.admin,
            start_date=today,
            end_date=today + timedelta(days=10),
            status="active",
        )
        self.autre_campagne = CampagneDistribution.objects.create(
            name="Campagne 02",
            created_by=self.admin,
            start_date=today,
            end_date=today + timedelta(days=10),
            status="active",
        )
        self.distribution = Distribution.objects.create(
            campagne=self.campagne, lieu=self.lieu,
            quantite=50, is_distributed=True,
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=self.autre_lieu, quantite=20
        )
        Distribution.objects.create(
            campagne=self.autre_campagne, lieu=self.lieu, quantite=70
        )
        self.url = reverse(
            "distribution:retirer_lieu_campagne",
            args=[self.campagne.pk, self.distribution.pk],
        )

    def test_denied_for_normal_user(self):
        self.client.login(username="normal", password="testpass123")
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertTrue(
            Distribution.objects.filter(pk=self.distribution.pk).exists()
        )

    def test_retirer_success_with_totals(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["removed"])
        self.assertEqual(data["commune_id"], self.commune.pk)
        # Le lieu retiré (50 docs validés) sort des compteurs.
        self.assertEqual(data["total_quantite"], 20)
        self.assertEqual(data["quantite_distribuee"], 0)
        self.assertEqual(data["commune_total_quantite"], 20)
        # Ligne supprimée, exclusion tracée, lieu conservé.
        self.assertFalse(
            Distribution.objects.filter(pk=self.distribution.pk).exists()
        )
        exclusion = CampagneLieuExclusion.objects.get(
            campagne=self.campagne, lieu=self.lieu
        )
        self.assertEqual(exclusion.excluded_by, self.admin)
        self.assertTrue(Lieu.objects.filter(pk=self.lieu.pk).exists())
        self.lieu.refresh_from_db()
        self.assertTrue(self.lieu.is_active)
        # Autre campagne intacte.
        autre = Distribution.objects.get(
            campagne=self.autre_campagne, lieu=self.lieu
        )
        self.assertEqual(autre.quantite, 70)

    def test_retirer_idempotent(self):
        self.client.login(username="admin", password="admin123")
        self.assertEqual(self.client.post(self.url).status_code, 200)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertFalse(data["removed"])

    def test_retirer_scoped_to_campagne(self):
        autre = Distribution.objects.get(
            campagne=self.autre_campagne, lieu=self.lieu
        )
        bad_url = reverse(
            "distribution:retirer_lieu_campagne",
            args=[self.campagne.pk, autre.pk],
        )
        self.client.login(username="admin", password="admin123")
        self.assertEqual(self.client.post(bad_url).status_code, 404)
        self.assertTrue(Distribution.objects.filter(pk=autre.pk).exists())

    def test_sync_skips_excluded_lieux(self):
        self.client.login(username="admin", password="admin123")
        self.client.post(self.url)
        nouveau = Lieu.objects.create(
            commune=self.commune, name="Salle des fêtes"
        )
        sync_url = reverse(
            "distribution:sync_campagne_lieux", args=[self.campagne.pk]
        )
        response = self.client.post(sync_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["created_count"], 1)
        self.assertEqual(data["skipped_count"], 1)
        self.assertIn("ignoré(s) car retiré(s)", data["message"])
        # Le lieu retiré n'est pas recréé, le nouveau oui.
        self.assertFalse(
            Distribution.objects.filter(
                campagne=self.campagne, lieu=self.lieu
            ).exists()
        )
        self.assertTrue(
            Distribution.objects.filter(
                campagne=self.campagne, lieu=nouveau
            ).exists()
        )

    def test_reintegrer_restores_zero_distribution(self):
        self.client.login(username="admin", password="admin123")
        self.client.post(self.url)
        reintegrer_url = reverse(
            "distribution:reintegrer_lieu_campagne",
            args=[self.campagne.pk, self.lieu.pk],
        )
        response = self.client.post(reintegrer_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        restored = Distribution.objects.get(
            campagne=self.campagne, lieu=self.lieu
        )
        self.assertEqual(restored.quantite, 0)
        self.assertFalse(restored.is_distributed)
        self.assertFalse(
            CampagneLieuExclusion.objects.filter(
                campagne=self.campagne, lieu=self.lieu
            ).exists()
        )

    def test_reintegrer_without_exclusion_404(self):
        self.client.login(username="admin", password="admin123")
        reintegrer_url = reverse(
            "distribution:reintegrer_lieu_campagne",
            args=[self.campagne.pk, self.autre_lieu.pk],
        )
        self.assertEqual(self.client.post(reintegrer_url).status_code, 404)

    def test_detail_shows_retirer_buttons_and_excluded(self):
        self.client.login(username="admin", password="admin123")
        detail_url = reverse(
            "distribution:campagne_detail", args=[self.campagne.pk]
        )
        content = self.client.get(detail_url).content.decode()
        self.assertIn("retirer-lieu-btn", content)
        self.client.post(self.url)
        content = self.client.get(detail_url).content.decode()
        content = html.unescape(content)
        self.assertIn("Lieux retirés de cette campagne (1)", content)
        self.assertIn("Le36", content)
        # Compteurs sans le lieu retiré : 1 lieu restant à 20 docs.
        self.assertIn("0/20 docs", content)

    def test_detail_docs_bar_uses_integer_width(self):
        # Non-régression : un pourcentage fractionnaire (ex. 678/1898)
        # ne doit pas rendre "width: 35,7%" (virgule locale invalide en
        # CSS, barre affichée pleine) mais une largeur entière.
        self.autre_lieu_dist = Distribution.objects.get(
            campagne=self.campagne, lieu=self.autre_lieu
        )
        self.autre_lieu_dist.is_distributed = True
        self.autre_lieu_dist.distributed_by = self.admin
        self.autre_lieu_dist.save()
        lieu_x = Lieu.objects.create(commune=self.commune, name="Lieu X")
        lieu_y = Lieu.objects.create(commune=self.commune, name="Lieu Y")
        Distribution.objects.create(
            campagne=self.campagne, lieu=lieu_x,
            quantite=608, is_distributed=True,
        )
        Distribution.objects.create(
            campagne=self.campagne, lieu=lieu_y, quantite=1220
        )
        # Total : 50+20+608+1220 = 1898, distribués : 50+20+608 = 678.
        self.client.login(username="admin", password="admin123")
        content = self.client.get(
            reverse("distribution:campagne_detail", args=[self.campagne.pk])
        ).content.decode()
        self.assertIn("678/1898 documents", html.unescape(content))
        self.assertIn('id="global-docs-progress-bar"', content)
        self.assertNotIn("35,7%", content)
        self.assertIn('style="width: 36%"', content)
