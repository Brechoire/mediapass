from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from .models import Location, VisitorCount


def create_mediatheque_group():
    group, _ = Group.objects.get_or_create(name="mediatheque")
    return group


def first_detailed_cell(months):
    """Première cellule du calendrier possédant une infobule détaillée."""
    for month in months:
        for week in month["weeks"]:
            for cell in week:
                if cell and cell.get("details"):
                    return cell
    return None


class VisitorStatisticsViewTests(TestCase):
    """Tests pour la vue statistics."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.user.groups.add(self.group)

        self.loc1 = Location.objects.create(
            name="Médiathèque", color="#4a6fa5", icon="bx-building", is_active=True, order=1, user=self.user
        )
        self.loc2 = Location.objects.create(
            name="Ludothèque", color="#10b981", icon="bx-game", is_active=True, order=2, user=self.user
        )

        today = timezone.now().date()
        for i in range(10):
            VisitorCount.objects.create(
                location=self.loc1, date=today - timedelta(days=i), count=10 + i, created_by=self.user
            )
            VisitorCount.objects.create(
                location=self.loc2, date=today - timedelta(days=i), count=5 + i, created_by=self.user
            )

    def login(self):
        self.client.login(username="mediat", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertEqual(response.status_code, 200)

    def test_contains_stats(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertContains(response, "Total visiteurs")
        self.assertContains(response, "Moyenne")
        self.assertContains(response, "Record")

    def test_best_day_shown(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertContains(response, "Meilleur jour")

    def test_top_locations(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertContains(response, "Médiathèque")
        self.assertContains(response, "Ludothèque")

    def test_filter_by_location(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/statistics/?location={self.loc1.id}")
        self.assertEqual(response.status_code, 200)

    def test_period_filter(self):
        self.login()
        for p in ["7_days", "30_days", "this_month", "last_month", "this_year"]:
            response = self.client.get(f"/mediatheque/visiteurs/statistics/?period={p}")
            self.assertEqual(response.status_code, 200, f"Failed for period={p}")

    def test_compare_locations(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/statistics/?location={self.loc1.id}&compare={self.loc2.id}"
        )
        self.assertEqual(response.status_code, 200)

    def test_weekday_averages(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertContains(response, "Lundi")

    def test_redirects_without_login(self):
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertEqual(response.status_code, 302)

    def test_top_days_table(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/statistics/")
        self.assertContains(response, "Top 5")


class VisitorIndexViewTests(TestCase):
    """Tests pour la vue index (pointage)."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.user.groups.add(self.group)

        self.loc = Location.objects.create(
            name="Médiathèque", color="#4a6fa5", icon="bx-building", is_active=True, order=1, user=self.user
        )

    def login(self):
        self.client.login(username="mediat", password="pass")

    def test_returns_200(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/")
        self.assertEqual(response.status_code, 200)

    def test_contains_title(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/")
        self.assertContains(response, "Pointage visiteurs")

    def test_contains_location_name(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/")
        self.assertContains(response, "Médiathèque")

    def test_redirects_without_login(self):
        response = self.client.get("/mediatheque/visiteurs/")
        self.assertEqual(response.status_code, 302)

    def test_has_increment_buttons(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/")
        self.assertContains(response, "+1")


class SpaceEditViewTests(TestCase):
    """Tests pour la vue d'édition d'espace."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.user.groups.add(self.group)

        self.other_user = User.objects.create_user(username="other", password="pass")
        self.other_user.groups.add(self.group)

        self.location = Location.objects.create(
            name="Médiathèque", color="#4a6fa5", icon="bx-building",
            is_active=True, order=1, user=self.user,
            description="Espace principal",
        )
        self.other_location = Location.objects.create(
            name="Autre", color="#ef4444", icon="bx-book",
            is_active=True, order=1, user=self.other_user,
        )

    def login(self):
        self.client.login(username="mediat", password="pass")

    def test_get_returns_200(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/")
        self.assertEqual(response.status_code, 200)

    def test_get_contains_prefilled_name(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/")
        self.assertContains(response, "Médiathèque")
        self.assertContains(response, "Espace principal")

    def test_get_contains_title(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/")
        self.assertContains(response, "Modifier")
        self.assertContains(response, "Enregistrer")

    def test_redirects_without_login(self):
        response = self.client.get(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/")
        self.assertEqual(response.status_code, 302)

    def test_edit_updates_location(self):
        self.login()
        response = self.client.post(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/", {
            "name": "Médiathèque Renovée",
            "description": "Nouvelle description",
            "icon": "bx-library",
            "color": "#22C55E",
        })
        self.assertRedirects(response, "/mediatheque/visiteurs/")
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Médiathèque Renovée")
        self.assertEqual(self.location.description, "Nouvelle description")
        self.assertEqual(self.location.icon, "bx-library")
        self.assertEqual(self.location.color, "#22C55E")

    def test_edit_rejects_empty_name(self):
        self.login()
        response = self.client.post(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/", {
            "name": "",
            "description": "",
            "icon": "bx-building",
            "color": "#4F46E5",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obligatoire")
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Médiathèque")

    def test_edit_rejects_duplicate_name_excluding_self(self):
        Location.objects.create(
            name="Ludothèque", color="#10b981", icon="bx-game",
            is_active=True, order=2, user=self.user,
        )
        self.login()
        response = self.client.post(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/", {
            "name": "Ludothèque",
            "description": "",
            "icon": "bx-building",
            "color": "#4F46E5",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "existe déjà")
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Médiathèque")

    def test_edit_saves_same_name_no_duplicate_error(self):
        self.login()
        response = self.client.post(f"/mediatheque/visiteurs/spaces/edit/{self.location.id}/", {
            "name": "Médiathèque",
            "description": "Mise à jour",
            "icon": "bx-building",
            "color": "#4a6fa5",
        })
        self.assertRedirects(response, "/mediatheque/visiteurs/")
        self.location.refresh_from_db()
        self.assertEqual(self.location.description, "Mise à jour")

    def test_edit_returns_404_for_other_user_location(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/spaces/edit/{self.other_location.id}/")
        self.assertEqual(response.status_code, 404)


class HeatmapViewTests(TestCase):
    """Tests pour la vue heatmap."""

    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="mediatheque")
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.user.groups.add(self.group)
        self.today = timezone.now().date()
        self.year = self.today.year

        self.loc = Location.objects.create(
            name="Médiathèque", color="#4a6fa5", icon="bx-building", is_active=True, order=1, user=self.user
        )

        # Un jour avec données pour chaque mois de l'année courante
        for m in range(1, 13):
            d = date(self.year, m, 1)
            VisitorCount.objects.create(location=self.loc, date=d, count=m * 10, created_by=self.user)

    def login(self):
        self.client.login(username="mediat", password="pass")

    def test_redirects_without_login(self):
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.status_code, 302)

    def test_returns_200(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.status_code, 200)

    def test_contains_months(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertContains(response, "Janvier")
        self.assertContains(response, "Décembre")

    def test_contains_year_title(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertContains(response, str(self.year))

    def test_custom_year_parameter(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/2024/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2024")

    def test_has_location_filter(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertContains(response, "Tous")
        self.assertContains(response, "Médiathèque")

    def test_location_filter_works(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/?location={self.loc.id}")
        self.assertEqual(response.status_code, 200)

    def test_context_year(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.context["year"], self.year)

    def test_context_months_count(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(len(response.context["months"]), 12)

    def test_context_max_count(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertGreater(response.context["max_count"], 0)

    def test_prev_next_year_links(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.context["prev_year"], self.year - 1)
        self.assertEqual(response.context["next_year"], self.year + 1)

    def test_mediatheque_required(self):
        other_user = User.objects.create_user(username="other", password="pass")
        self.client.login(username="other", password="pass")
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.status_code, 302)

    def test_no_data_returns_200(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/heatmap/2020/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["max_count"], 0)

    def _create_superuser_context(self):
        """Superuser + deuxième commune avec ses propres données."""
        self.superuser = User.objects.create_superuser(
            username="admin", password="pass", email="admin@example.com"
        )
        self.superuser.groups.add(self.group)
        self.other = User.objects.create_user(username="anor", password="pass")
        self.loc_anor = Location.objects.create(
            name="Médiathèque Anor",
            color="#10b981",
            icon="bx-building",
            is_active=True,
            order=2,
            user=self.other,
        )
        for m in range(1, 13):
            VisitorCount.objects.create(
                location=self.loc_anor, date=date(self.year, m, 1), count=m
            )

    def test_superuser_global_view(self):
        self._create_superuser_context()
        self.client.login(username="admin", password="pass")
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["commune"], "")
        self.assertEqual(len(response.context["available_communes"]), 2)
        # Vue globale : totaux sommés par date (1er déc. : 120 de "mediat" + 12 d'"anor")
        self.assertEqual(response.context["max_count"], 132)
        self.assertTrue(response.context["show_commune_prefix"])

    def test_superuser_commune_filter(self):
        self._create_superuser_context()
        self.client.login(username="admin", password="pass")
        response = self.client.get(
            f"/mediatheque/visiteurs/heatmap/{self.year}/?commune=anor"
        )
        self.assertEqual(response.context["commune"], "anor")
        # Max limité à la commune anor (décembre = 12)
        self.assertEqual(response.context["max_count"], 12)
        locations = list(response.context["locations"])
        self.assertEqual([loc.name for loc in locations], ["Médiathèque Anor"])
        self.assertFalse(response.context["show_commune_prefix"])

    def test_invalid_commune_ignored(self):
        self._create_superuser_context()
        self.client.login(username="admin", password="pass")
        response = self.client.get(
            f"/mediatheque/visiteurs/heatmap/{self.year}/?commune=inconnue"
        )
        self.assertEqual(response.context["commune"], "")
        self.assertEqual(response.context["max_count"], 132)

    def test_regular_user_no_commune_dropdown(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertEqual(response.context["available_communes"], [])
        self.assertEqual(response.context["commune"], "")

    def test_superuser_back_link(self):
        self._create_superuser_context()
        self.client.login(username="admin", password="pass")
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertContains(response, "Retour aux statistiques")
        self.assertNotContains(response, "Retour au pointage")

    def test_regular_user_back_link(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        self.assertContains(response, "Retour au pointage")

    def test_tooltip_espace_only_for_regular_user(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/heatmap/{self.year}/")
        cell = first_detailed_cell(response.context["months"])
        self.assertIsNotNone(cell)
        # Utilisateur simple : « Espace - N visiteur(s) », pas de commune
        self.assertTrue(cell["details"].startswith("Médiathèque"))
        self.assertNotIn("- Médiathèque", cell["details"])


class SuperadminHeatmapViewTests(TestCase):
    """Tests pour le calendrier de fréquentation superadmin."""

    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="mediatheque")
        self.year = timezone.now().year

        # Superuser volontairement HORS groupe mediatheque
        self.admin = User.objects.create_superuser(
            username="adminhm", password="pass", email="adminhm@example.com"
        )
        self.mediat = User.objects.create_user(username="mediat", password="pass")
        self.mediat.groups.add(self.group)
        self.loc_mediat = Location.objects.create(
            name="Médiathèque",
            color="#4a6fa5",
            icon="bx-building",
            is_active=True,
            order=1,
            user=self.mediat,
        )
        self.anor = User.objects.create_user(username="anor", password="pass")
        self.loc_anor = Location.objects.create(
            name="Médiathèque Anor",
            color="#10b981",
            icon="bx-building",
            is_active=True,
            order=2,
            user=self.anor,
        )
        for m in range(1, 13):
            VisitorCount.objects.create(
                location=self.loc_mediat, date=date(self.year, m, 1), count=m * 10
            )
            VisitorCount.objects.create(
                location=self.loc_anor, date=date(self.year, m, 1), count=m
            )

    def login(self):
        self.client.login(username="adminhm", password="pass")

    def test_admin_access_without_group(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/admin-heatmap/{self.year}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["months"]), 12)

    def test_redirects_non_superuser(self):
        self.client.login(username="mediat", password="pass")
        response = self.client.get(f"/mediatheque/visiteurs/admin-heatmap/{self.year}/")
        self.assertEqual(response.status_code, 302)

    def test_global_view_sums_communes(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/admin-heatmap/{self.year}/")
        self.assertEqual(response.context["commune"], "")
        # Totaux sommés par date (1er déc. : 120 + 12)
        self.assertEqual(response.context["max_count"], 132)
        self.assertTrue(response.context["show_commune_prefix"])
        self.assertIn(self.year, response.context["years"])

    def test_commune_filter(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/admin-heatmap/{self.year}/?commune=anor"
        )
        self.assertEqual(response.context["commune"], "anor")
        self.assertEqual(response.context["max_count"], 12)
        locations = list(response.context["locations"])
        self.assertEqual([loc.name for loc in locations], ["Médiathèque Anor"])
        self.assertFalse(response.context["show_commune_prefix"])

    def test_invalid_commune_ignored(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/admin-heatmap/{self.year}/?commune=inconnue"
        )
        self.assertEqual(response.context["commune"], "")
        self.assertEqual(response.context["max_count"], 132)

    def test_year_query_param(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-heatmap/?year=2024")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["year"], 2024)

    def test_global_tooltip_shows_commune(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/admin-heatmap/{self.year}/")
        cell = first_detailed_cell(response.context["months"])
        self.assertIsNotNone(cell)
        # Format « Commune - N visiteur(s) - Espace », communes triées
        self.assertTrue(cell["details"].startswith("Anor - "))
        self.assertIn("- Médiathèque", cell["details"])

    def test_commune_filter_tooltip_without_prefix(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/admin-heatmap/{self.year}/?commune=anor"
        )
        cell = first_detailed_cell(response.context["months"])
        self.assertIsNotNone(cell)
        # Format « Espace - N visiteur(s) » sans préfixe de commune
        self.assertTrue(cell["details"].startswith("Médiathèque Anor - "))
        self.assertNotIn(" - Médiathèque Anor", cell["details"])


class AnnualReportViewTests(TestCase):
    """Tests pour la vue rapport annuel."""

    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="mediatheque")
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.user.groups.add(self.group)
        self.today = timezone.now().date()
        self.year = self.today.year

        self.loc1 = Location.objects.create(
            name="Médiathèque", color="#4a6fa5", icon="bx-building", is_active=True, order=1, user=self.user
        )
        self.loc2 = Location.objects.create(
            name="Ludothèque", color="#10b981", icon="bx-game", is_active=True, order=2, user=self.user
        )

        for m in range(1, 13):
            d = date(self.year, m, 1)
            VisitorCount.objects.create(location=self.loc1, date=d, count=m * 10, created_by=self.user)
            VisitorCount.objects.create(location=self.loc2, date=d, count=m * 5, created_by=self.user)

        # Données N-1
        for m in range(1, 13):
            d = date(self.year - 1, m, 1)
            VisitorCount.objects.create(location=self.loc1, date=d, count=m * 8, created_by=self.user)

    def login(self):
        self.client.login(username="mediat", password="pass")

    def test_redirects_without_login(self):
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertEqual(response.status_code, 302)

    def test_returns_200(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertEqual(response.status_code, 200)

    def test_context_year(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertEqual(response.context["year"], self.year)

    def test_contains_yearly_total(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertContains(response, f"{self.loc1.name}")
        self.assertContains(response, f"{self.loc2.name}")

    def test_custom_year(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/report/2024/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["year"], 2024)

    def test_has_monthly_data(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        monthly = response.context["monthly"]
        self.assertEqual(len(monthly), 12)
        self.assertEqual(monthly[0]["total"], 15)

    def test_top_locations_present(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertIn("yearly_top", response.context)

    def test_prev_next_year_in_context(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertEqual(response.context["prev_year"], self.year - 1)
        self.assertEqual(response.context["next_year"], self.year + 1)

    def test_mediatheque_required(self):
        other = User.objects.create_user(username="other", password="pass")
        self.client.login(username="other", password="pass")
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertEqual(response.status_code, 302)


class SuperadminStatisticsViewTests(TestCase):
    """Tests pour la vue superadmin_statistics avec filtre par commune."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", password="pass", email="admin@example.com"
        )
        self.anor = User.objects.create_user(username="anor", password="pass")
        self.trelon = User.objects.create_user(username="trelon", password="pass")

        self.loc_anor = Location.objects.create(
            name="Médiathèque Anor",
            color="#4a6fa5",
            icon="bx-building",
            is_active=True,
            order=1,
            user=self.anor,
        )
        self.loc_trelon = Location.objects.create(
            name="Médiathèque Trélon",
            color="#10b981",
            icon="bx-building",
            is_active=True,
            order=1,
            user=self.trelon,
        )

        today = timezone.now().date()
        VisitorCount.objects.create(
            location=self.loc_anor,
            date=today - timedelta(days=1),
            count=30,
            created_by=self.anor,
        )
        VisitorCount.objects.create(
            location=self.loc_trelon,
            date=today - timedelta(days=1),
            count=50,
            created_by=self.trelon,
        )

    def login(self):
        self.client.login(username="admin", password="pass")

    def test_requires_superuser(self):
        self.anor.groups.add(create_mediatheque_group())
        self.client.login(username="anor", password="pass")
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        # Redirection (login_required) ou refus (user_passes_test)
        self.assertIn(response.status_code, [302, 403])

    def test_global_stats_without_filter(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["global_stats"]["total"], 80)
        self.assertEqual(response.context["commune"], "")
        self.assertEqual(len(response.context["available_communes"]), 2)

    def test_filter_by_commune(self):
        self.login()
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/?commune=anor"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["commune"], "anor")
        self.assertEqual(response.context["global_stats"]["total"], 30)
        # Le comparatif est masqué quand une commune est sélectionnée
        self.assertEqual(response.context["users_comparison"], [])
        self.assertEqual(response.context["available_users"], [])

    def test_filter_other_commune(self):
        self.login()
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/?commune=trelon"
        )
        self.assertEqual(response.context["global_stats"]["total"], 50)
        # Détail par espace limité à la commune filtrée
        locations = response.context["locations"]
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]["name"], "Médiathèque Trélon")

    def test_invalid_commune_ignored(self):
        self.login()
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/?commune=inconnue"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["commune"], "")
        self.assertEqual(response.context["global_stats"]["total"], 80)

    def test_comparison_still_available_globally(self):
        self.login()
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/?users=anor&users=trelon"
        )
        users_comparison = response.context["users_comparison"]
        self.assertEqual(len(users_comparison), 2)
        self.assertIsNotNone(response.context["duel"])

    @staticmethod
    def last_open_day(reference=None):
        """Date la plus récente (< reference) qui n'est pas un dimanche."""
        d = (reference or timezone.now().date()) - timedelta(days=1)
        while d.weekday() == 6:
            d -= timedelta(days=1)
        return d

    def test_custom_period(self):
        self.login()
        d = self.last_open_day()
        VisitorCount.objects.update_or_create(
            location=self.loc_anor, date=d, defaults={"count": 7}
        )
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/"
            f"?period=custom&start_date={d.isoformat()}&end_date={d.isoformat()}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period"], "custom")
        # Anor (7) + Trelon (50) sur la même date
        self.assertEqual(response.context["global_stats"]["total"], 57)

        # Combiné avec le filtre commune
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/"
            f"?period=custom&start_date={d.isoformat()}&end_date={d.isoformat()}"
            "&commune=anor"
        )
        self.assertEqual(response.context["global_stats"]["total"], 7)

    def test_custom_period_invalid_dates_fallback(self):
        self.login()
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/"
            "?period=custom&start_date=oops&end_date=oops"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period_length"], 30)

    def test_prev_period_comparison(self):
        self.login()
        d = self.last_open_day()
        prev_d = d - timedelta(days=30)
        VisitorCount.objects.update_or_create(
            location=self.loc_anor, date=d, defaults={"count": 12}
        )
        VisitorCount.objects.update_or_create(
            location=self.loc_anor, date=prev_d, defaults={"count": 11}
        )
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        labels = list(response.context["chart_labels"])
        ix = labels.index(d.isoformat())
        prev_values = list(response.context["chart_prev_values"])
        self.assertEqual(len(prev_values), len(labels))
        self.assertEqual(prev_values[ix], 11)

    def test_weekly_and_best_week_context(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        self.assertTrue(len(response.context["week_labels"]) >= 1)
        self.assertEqual(
            len(response.context["week_values"]),
            len(response.context["week_labels"]),
        )
        # Période par défaut = 30 jours → fenêtre de 7 jours toujours possible
        self.assertIsNotNone(response.context["best_week"])
        self.assertIsNotNone(response.context["worst_week"])

    def test_n1_context(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("n1_total", response.context)
        self.assertIn("n1_variation", response.context)

    def test_header_links(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        self.assertContains(response, "Heatmap")
        self.assertContains(response, "Rapport")
        self.assertNotContains(response, "Retour au pointage")

    def test_projection_this_month(self):
        self.login()
        today = timezone.now().date()
        if (today - timedelta(days=1)).weekday() != 6:
            response = self.client.get(
                "/mediatheque/visiteurs/admin-statistics/?period=this_month"
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("projection", response.context)
