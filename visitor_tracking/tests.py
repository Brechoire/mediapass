import json
from datetime import date, timedelta
from io import BytesIO

from accounts.models import LibraryProfile
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from docx import Document as DocxDocument

from .models import Closure, Location, VisitorCount
from .opening import (
    build_closure_map,
    get_open_dates,
    get_opening_weekdays,
    group_dates_into_ranges,
)
from .reporting import AnnualReportService


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

    def test_rich_tooltip_map(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/admin-heatmap/{self.year}/")
        tips = response.context["heatmap_tooltips"]
        # 1er déc. : 120 + 12 = 132 visiteurs, 2 lignes de détail.
        key = f"{self.year}-12-01"
        self.assertIn(key, tips)
        self.assertEqual(tips[key]["total"], 132)
        self.assertIn("décembre", tips[key]["label"])
        self.assertEqual(len(tips[key]["lines"]), 2)
        self.assertGreaterEqual(tips[key]["lines"][0]["count"], 0)

    def test_rich_tooltip_markup(self):
        import re

        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/admin-heatmap/{self.year}/")
        content = response.content.decode()
        self.assertIn('id="heatmap-tooltips"', content)
        self.assertIn('id="heatmap-tip"', content)
        self.assertContains(response, "Survolez ou touchez un jour")
        m = re.search(r'<div class="heatmap-cell[^>]*>', content)
        self.assertIsNotNone(m)
        cell_tag = m.group(0)
        self.assertIn("data-date=", cell_tag)
        self.assertIn("aria-label=", cell_tag)
        self.assertIn('tabindex="0"', cell_tag)
        # Plus de title natif sur les cellules (infobulle custom à la place).
        self.assertNotIn("title=", cell_tag)


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
        # Pas de navigation vers une année future.
        self.assertIsNone(response.context["next_year"])

    def test_past_year_has_next_year(self):
        self.login()
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year - 1}/")
        self.assertEqual(response.context["prev_year"], self.year - 2)
        self.assertEqual(response.context["next_year"], self.year)

    def test_mediatheque_required(self):
        other = User.objects.create_user(username="other", password="pass")
        self.client.login(username="other", password="pass")
        response = self.client.get(f"/mediatheque/visiteurs/report/{self.year}/")
        self.assertEqual(response.status_code, 302)


    def test_default_view_is_synthesis(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year}/"
        )
        content = response.content.decode()
        self.assertIn("Synthèse", content)
        self.assertNotIn("Détail par espace", content)

    def test_detail_view(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year}/?vue=detail"
        )
        content = response.content.decode()
        self.assertIn("Détail par espace", content)
        self.assertIn("Meilleurs jours", content)

    def test_template_accessibility(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year}/"
        )
        content = response.content.decode()
        self.assertIn('scope="col"', content)
        self.assertIn("<caption", content)
        self.assertIn('role="img"', content)

    def test_legacy_year_shows_method(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year - 1}/"
        )
        content = response.content.decode()
        self.assertIn("Méthode historique", content)

    def test_report_shows_closures(self):
        Closure.objects.create(
            user=self.user,
            start_date=date(self.year, 1, 2),
            end_date=date(self.year, 1, 3),
            kind="annual",
            label="Fermeture test",
        )
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year}/?vue=detail"
        )
        content = response.content.decode()
        self.assertIn("Fermetures", content)
        self.assertIn("Fermeture annuelle", content)
        self.assertIn("Jours d'ouverture", content)

    def test_member_commune_is_ignored(self):
        self.login()
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year}/?commune=autre"
        )
        self.assertEqual(
            response.context["report"]["scope"]["username"], "mediat"
        )

    def test_superadmin_requires_commune(self):
        superuser = User.objects.create_superuser(
            username="admin", password="pass"
        )
        superuser.groups.add(self.group)
        self.client.login(username="admin", password="pass")
        response = self.client.get("/mediatheque/visiteurs/report/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Choisissez la médiathèque",
            response.content.decode(),
        )

    def test_superadmin_with_commune(self):
        superuser = User.objects.create_superuser(
            username="admin", password="pass"
        )
        superuser.groups.add(self.group)
        self.client.login(username="admin", password="pass")
        response = self.client.get(
            f"/mediatheque/visiteurs/report/{self.year}/?commune=mediat"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["report"]["scope"]["username"], "mediat"
        )


@override_settings(VISITOR_REPORT_V2_FROM_YEAR=2026)
class AnnualReportServiceTests(TestCase):
    """Règles de calcul du rapport annuel par médiathèque."""

    def setUp(self):
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.loc_a = Location.objects.create(
            name="Médiathèque",
            color="#4a6fa5",
            icon="bx-building",
            is_active=True,
            order=1,
            user=self.user,
        )
        self.loc_b = Location.objects.create(
            name="Ludothèque",
            color="#10b981",
            icon="bx-game",
            is_active=True,
            order=2,
            user=self.user,
        )
        # 2026-01-05 = lundi, 2026-01-06 = mardi, 2026-01-11 = dimanche.
        VisitorCount.objects.create(
            location=self.loc_a, date=date(2026, 1, 5), count=10
        )
        VisitorCount.objects.create(
            location=self.loc_a, date=date(2026, 1, 6), count=20
        )
        VisitorCount.objects.create(
            location=self.loc_a, date=date(2026, 1, 11), count=5
        )
        VisitorCount.objects.create(
            location=self.loc_b, date=date(2026, 1, 5), count=7
        )
        VisitorCount.objects.create(
            location=self.loc_a, date=date(2025, 1, 5), count=10
        )
        self.today = date(2026, 11, 23)

    def build(self, year=2026):
        return AnnualReportService(
            year, self.user, today=self.today
        ).build()

    def test_sunday_is_kept_in_total_but_not_in_expected_days(self):
        report = self.build()
        totals = report["totals"]
        self.assertEqual(totals["total"], 42)
        self.assertEqual(totals["pointed_days"], 3)
        self.assertEqual(totals["sunday_days"], 1)
        self.assertEqual(totals["sunday_total"], 5)
        self.assertEqual(totals["weekday_pointed_days"], 2)
        self.assertEqual(totals["avg_per_pointed_day"], 14.0)
        self.assertEqual(totals["avg_per_open_day"], 18.5)
        self.assertEqual(
            totals["missing_days"],
            totals["expected_days"] - 2,
        )

    def test_no_sunday_pointage_does_not_require_sunday(self):
        VisitorCount.objects.filter(date=date(2026, 1, 11)).delete()
        report = self.build()
        totals = report["totals"]
        self.assertEqual(totals["total"], 37)
        self.assertEqual(totals["sunday_days"], 0)
        self.assertEqual(totals["pointed_days"], 2)
        self.assertEqual(totals["weekday_pointed_days"], 2)
        self.assertEqual(
            totals["missing_days"],
            totals["expected_days"] - 2,
        )

    def test_partial_year_stops_today_and_compares_same_period(self):
        report = self.build()
        self.assertTrue(report["period"]["is_partial"])
        self.assertEqual(report["period"]["end"], self.today)
        self.assertEqual(report["period"]["n1_label"], "à date comparable")
        self.assertEqual(report["period"]["n1_year"], 2025)
        self.assertEqual(report["totals"]["n1_total"], 10)
        self.assertEqual(report["totals"]["variation"], 320.0)

    def test_legacy_year_keeps_historical_method(self):
        report = self.build(year=2025)
        self.assertEqual(report["period"]["method"], "legacy")
        self.assertIsNone(report["totals"]["expected_days"])
        self.assertIsNone(report["totals"]["completeness"])
        self.assertEqual(report["totals"]["total"], 10)

    def test_top_days_are_unique_by_date(self):
        report = self.build()
        dates = [item["date"] for item in report["top_days"]]
        self.assertEqual(len(dates), len(set(dates)))
        jan_5 = next(
            item
            for item in report["top_days"]
            if item["date"] == date(2026, 1, 5)
        )
        self.assertEqual(jan_5["total"], 17)
        self.assertEqual(len(jan_5["spaces"]), 2)

    def test_homonym_locations_are_not_merged(self):
        loc_c = Location.objects.create(
            name="Médiathèque",
            color="#7c3aed",
            is_active=True,
            order=3,
            user=self.user,
        )
        VisitorCount.objects.create(
            location=loc_c, date=date(2026, 1, 5), count=3
        )
        report = self.build()
        homonyms = [
            space
            for space in report["spaces"]
            if space["name"] == "Médiathèque"
        ]
        self.assertEqual(len(homonyms), 2)
        self.assertEqual({space["total"] for space in homonyms}, {35, 3})

    def test_spaces_without_data_are_listed(self):
        loc_c = Location.objects.create(
            name="Animation",
            color="#f97316",
            is_active=True,
            order=3,
            user=self.user,
        )
        report = self.build()
        space = next(
            item for item in report["spaces"] if item["id"] == loc_c.id
        )
        self.assertEqual(space["total"], 0)
        self.assertFalse(space["has_data"])
        self.assertIn(
            loc_c.id,
            [item["id"] for item in report["spaces_without_data"]],
        )

    def test_perimetre_and_method_note(self):
        report = self.build()
        self.assertIn("Mediat", report["synthese"]["perimetre"])
        self.assertIn("Médiathèque", report["synthese"]["perimetre"])
        self.assertIn("recalculé", report["period"]["n1_method_note"])
        self.assertGreaterEqual(len(report["synthese"]["phrases"]), 5)

    def test_n1_without_data_is_flagged(self):
        VisitorCount.objects.filter(date__year=2025).delete()
        report = self.build()
        self.assertFalse(report["totals"]["n1_has_data"])
        self.assertIsNone(report["totals"]["variation"])
        self.assertEqual(report["period"]["n1_method_note"], "")


@override_settings(VISITOR_REPORT_V2_FROM_YEAR=2026)
class AnnualReportExportTests(TestCase):
    """Exports DOCX, CSV et impression du rapport annuel."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(username="mediat", password="pass")
        self.user.groups.add(self.group)
        self.today = timezone.now().date()
        self.year = self.today.year
        self.loc = Location.objects.create(
            name="Médiathèque",
            color="#4a6fa5",
            icon="bx-building",
            is_active=True,
            order=1,
            user=self.user,
        )
        days = []
        cursor = date(self.year, 1, 1)
        while len(days) < 2:
            if cursor.weekday() != 6:
                days.append(cursor)
            cursor += timedelta(days=1)
        VisitorCount.objects.create(
            location=self.loc, date=days[0], count=12
        )
        VisitorCount.objects.create(
            location=self.loc, date=days[1], count=8
        )

    def login(self):
        self.client.login(username="mediat", password="pass")

    def test_docx_synthese(self):
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "docx-synthese"],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("wordprocessingml", response["Content-Type"])
        self.assertIn("bilan_", response["Content-Disposition"])
        document = DocxDocument(BytesIO(response.content))
        text = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
        self.assertIn("Bilan d'activité", text)
        self.assertIn("Synthèse", text)
        self.assertGreaterEqual(len(document.tables), 2)

    def test_docx_detail_contains_annex(self):
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "docx-detail"],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("rapport_", response["Content-Disposition"])
        document = DocxDocument(BytesIO(response.content))
        text = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
        self.assertIn("Rapport d'activité", text)
        self.assertIn("Sommaire", text)
        self.assertIn(
            "Annexe — Répartition mensuelle par espace", text
        )
        self.assertGreaterEqual(len(document.tables), 5)

    def test_csv_synthese(self):
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "csv-synthese"],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("Type;Libellé;Total;N-1;Variation (%);Part (%)", content)
        self.assertIn("Mois;Janvier", content)
        self.assertIn("Espace;Médiathèque", content)

    def test_csv_synthese_includes_closures(self):
        day = date(self.year, 2, 1)
        while day.weekday() == 6:
            day += timedelta(days=1)
        Closure.objects.create(
            user=self.user,
            start_date=day,
            end_date=day,
            kind="annual",
            label="Fermeture test",
        )
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "csv-synthese"],
            )
        )
        content = response.content.decode("utf-8-sig")
        self.assertIn("Fermeture;Fermeture annuelle — Fermeture test", content)

    def test_docx_detail_includes_closures(self):
        day = date(self.year, 2, 1)
        while day.weekday() == 6:
            day += timedelta(days=1)
        Closure.objects.create(
            user=self.user,
            start_date=day,
            end_date=day,
            kind="annual",
            label="Fermeture test",
        )
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "docx-detail"],
            )
        )
        self.assertEqual(response.status_code, 200)
        document = DocxDocument(BytesIO(response.content))
        text = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
        self.assertIn("Fermetures", text)
        self.assertGreaterEqual(len(document.tables), 6)

    def test_csv_donnees(self):
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "csv-donnees"],
            )
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertTrue(
            content.startswith("Date;Espace;Nombre de visiteurs")
        )
        self.assertIn("Médiathèque", content)

    def test_print_view(self):
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_print",
                args=[self.year],
            )
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Imprimer / PDF", content)
        self.assertIn("report-daily-chart", content)

    def test_superadmin_export_requires_commune(self):
        superuser = User.objects.create_superuser(
            username="admin", password="pass"
        )
        superuser.groups.add(self.group)
        self.client.login(username="admin", password="pass")
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "docx-synthese"],
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_superadmin_export_with_commune(self):
        superuser = User.objects.create_superuser(
            username="admin", password="pass"
        )
        superuser.groups.add(self.group)
        self.client.login(username="admin", password="pass")
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "docx-synthese"],
            )
            + "?commune=mediat"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("bilan_mediat_", response["Content-Disposition"])
        document = DocxDocument(BytesIO(response.content))
        text = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
        self.assertIn("Médiathèque", text)

    def test_member_commune_is_ignored(self):
        other = User.objects.create_user(username="autre", password="pass")
        other_loc = Location.objects.create(
            name="Autre médiathèque",
            user=other,
            is_active=True,
        )
        VisitorCount.objects.create(
            location=other_loc, date=self.today, count=99
        )
        self.login()
        response = self.client.get(
            reverse(
                "visitor_tracking:annual_report_export",
                args=[self.year, "csv-donnees"],
            )
            + "?commune=autre"
        )
        content = response.content.decode("utf-8-sig")
        self.assertIn("Médiathèque", content)
        self.assertNotIn("Autre médiathèque", content)


class SuperadminStatisticsViewTests(TestCase):
    """Tests pour la vue superadmin_statistics avec filtre par commune."""

    @staticmethod
    def last_open_day(reference=None):
        """Date la plus récente (< reference) qui n'est pas un dimanche."""
        d = (reference or timezone.now().date()) - timedelta(days=1)
        while d.weekday() == 6:
            d -= timedelta(days=1)
        return d

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

        # Jour ouvré (pas un dimanche : les dimanches sont exclus des stats).
        day = self.last_open_day()
        VisitorCount.objects.create(
            location=self.loc_anor,
            date=day,
            count=30,
            created_by=self.anor,
        )
        VisitorCount.objects.create(
            location=self.loc_trelon,
            date=day,
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
        # Décision produit : plus de mode duel, comparaisons à N.
        self.assertNotIn("duel", response.context)
        content = response.content.decode()
        self.assertNotIn("Mode duel", content)
        self.assertNotIn("Différence (1 vs 2)", content)

    def test_layout_refonte_lot1(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        content = response.content.decode()
        # En-tête clair (plus de dégradé), fieldset, bouton Comparer.
        self.assertNotIn("from-[#4a6fa5]", content)
        self.assertIn("Filtres — combinables", content)
        self.assertIn("Filtrer", content)
        self.assertIn("Comparer", content)
        self.assertIn('href="#bloc-detail"', content)
        # Accessibilité tableaux et canvas.
        self.assertIn('scope="col"', content)
        self.assertIn("<caption", content)
        self.assertIn('role="img"', content)
        self.assertIn("integrity=", content)

    def test_commune_month_matrix(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        matrix = response.context["commune_month_matrix"]
        self.assertTrue(len(matrix["matrix"]) >= 2)
        for row in matrix["matrix"]:
            self.assertEqual(len(row["months"]), len(matrix["months"]))
            self.assertEqual(row["total"], sum(row["months"]))
            for cell in row["cells"]:
                self.assertIn("start", cell)
                self.assertIn("end", cell)
        content = response.content.decode()
        self.assertIn("Saisonnalité", content)
        self.assertIn("bloc-saisonnalite", content)

    def test_weekday_overview(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        overview = response.context["weekday_overview"]
        self.assertEqual(len(overview), 6)
        self.assertEqual(overview[0]["name"], "Lundi")
        self.assertTrue(all("total" in d and "avg" in d for d in overview))
        self.assertContains(response, "Moyennes par jour de semaine")

    def test_synthese_content(self):
        self.login()
        response = self.client.get("/mediatheque/visiteurs/admin-statistics/")
        synthese = response.context["synthese"]
        self.assertIsNone(synthese["perimetre"])
        phrases = synthese["phrases"]
        self.assertGreaterEqual(len(phrases), 8)
        self.assertLessEqual(len(phrases), 12)
        full = " ".join(phrases)
        self.assertIn("80", full)
        content = response.content.decode()
        self.assertIn("Synthèse", content)
        self.assertIn("synthese-phrase", content)
        self.assertIn("Exporter CSV", content)

    def test_synthese_with_commune_filter(self):
        self.login()
        response = self.client.get(
            "/mediatheque/visiteurs/admin-statistics/?commune=anor"
        )
        synthese = response.context["synthese"]
        self.assertIn("anor", (synthese["perimetre"] or "").lower())
        self.assertContains(response, "Périmètre :")

    def test_annual_report_synthese(self):
        self.superuser.groups.add(create_mediatheque_group())
        self.login()
        response = self.client.get("/mediatheque/visiteurs/report/?commune=anor")
        self.assertEqual(response.status_code, 200)
        self.assertIn("synthese", response.context)
        phrases = response.context["synthese"]["phrases"]
        self.assertGreaterEqual(len(phrases), 6)
        self.assertIn("Synthèse", response.content.decode())

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


class OpeningCalendarTests(TestCase):
    """Jours d'ouverture et fermetures."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="mediat", password="pass"
        )

    def test_default_opening_weekdays(self):
        self.assertEqual(
            get_opening_weekdays(self.user), [0, 1, 2, 3, 4, 5]
        )

    def test_profile_opening_weekdays(self):
        LibraryProfile.objects.create(
            user=self.user,
            name="Médiathèque",
            opening_weekdays=[0, 1, 2, 3, 4],
        )
        self.assertEqual(
            get_opening_weekdays(self.user), [0, 1, 2, 3, 4]
        )

    def test_invalid_weekdays_fall_back_to_default(self):
        LibraryProfile.objects.create(
            user=self.user,
            name="Médiathèque",
            opening_weekdays=["x", 9, -1],
        )
        self.assertEqual(
            get_opening_weekdays(self.user), [0, 1, 2, 3, 4, 5]
        )

    def test_open_dates_exclude_closure_and_sunday(self):
        Closure.objects.create(
            user=self.user,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 6),
            kind="annual",
        )
        closure_map = build_closure_map(
            self.user, date(2026, 1, 1), date(2026, 1, 11)
        )
        open_dates = get_open_dates(
            date(2026, 1, 1),
            date(2026, 1, 11),
            [0, 1, 2, 3, 4, 5],
            closure_map,
        )
        self.assertNotIn(date(2026, 1, 5), open_dates)
        self.assertNotIn(date(2026, 1, 6), open_dates)
        self.assertNotIn(date(2026, 1, 11), open_dates)
        self.assertIn(date(2026, 1, 7), open_dates)

    def test_group_dates_into_ranges(self):
        ranges = group_dates_into_ranges(
            [
                date(2026, 1, 1),
                date(2026, 1, 2),
                date(2026, 1, 3),
                date(2026, 1, 5),
            ]
        )
        self.assertEqual(
            ranges,
            [
                (date(2026, 1, 1), date(2026, 1, 3)),
                (date(2026, 1, 5), date(2026, 1, 5)),
            ],
        )

    def test_closure_map_priority(self):
        Closure.objects.create(
            user=self.user,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 5),
            kind="annual",
            label="Annuelle",
        )
        Closure.objects.create(
            user=self.user,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 5),
            kind="public_holiday",
            label="Férié",
        )
        closure_map = build_closure_map(
            self.user, date(2026, 1, 1), date(2026, 1, 31)
        )
        self.assertEqual(
            closure_map[date(2026, 1, 5)].kind, "public_holiday"
        )


@override_settings(VISITOR_REPORT_V2_FROM_YEAR=2026)
class HeatmapClosureTests(TestCase):
    """États de la heatmap et endpoints de qualification."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(
            username="mediat", password="pass"
        )
        self.user.groups.add(self.group)
        self.location = Location.objects.create(
            name="Médiathèque",
            user=self.user,
            is_active=True,
            order=1,
        )
        self.today = timezone.now().date()
        self.year = self.today.year
        self.client.login(username="mediat", password="pass")

    def _past_open_days(self, count=3):
        day = self.today - timedelta(days=1)
        days = []
        while len(days) < count:
            if day.weekday() != 6:
                days.append(day)
            day -= timedelta(days=1)
        return sorted(days)

    def test_missing_days_have_orange_state(self):
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context["missing_count"], 0)
        self.assertContains(response, "heatmap-missing")

    def test_closure_removes_missing_days(self):
        before = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
        ).context["missing_count"]
        days = self._past_open_days(2)
        Closure.objects.create(
            user=self.user,
            start_date=days[0],
            end_date=days[-1],
            kind="annual",
            label="Fermeture test",
        )
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
        )
        self.assertEqual(response.context["missing_count"], before - 2)
        self.assertContains(response, "heatmap-closed")

    def test_pointage_on_non_open_day_is_exceptional(self):
        day = self.today - timedelta(days=1)
        while day.weekday() != 6:
            day -= timedelta(days=1)
        VisitorCount.objects.create(
            location=self.location, date=day, count=4
        )
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
        )
        self.assertContains(response, "heatmap-exceptional")

    def test_sunday_toggle(self):
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
        )
        self.assertFalse(response.context["include_sunday"])
        self.assertEqual(
            len(response.context["months"][0]["weeks"][0]), 6
        )
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
            + "?dimanche=1"
        )
        self.assertTrue(response.context["include_sunday"])
        self.assertEqual(
            len(response.context["months"][0]["weeks"][0]), 7
        )
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
            + "?dimanche=0"
        )
        self.assertFalse(response.context["include_sunday"])

    def test_2025_is_read_only(self):
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[2025])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_validate"])
        self.assertContains(
            response, "disponible à partir de 2026"
        )

    def test_opening_days_update(self):
        response = self.client.post(
            reverse(
                "visitor_tracking:heatmap_opening_days",
                args=[self.year],
            ),
            {"weekdays": ["0", "1", "2", "3", "4"]},
        )
        self.assertEqual(response.status_code, 302)
        profile = LibraryProfile.objects.get(user=self.user)
        self.assertEqual(profile.opening_weekdays, [0, 1, 2, 3, 4])
        response = self.client.get(
            reverse("visitor_tracking:heatmap_year", args=[self.year])
        )
        self.assertEqual(
            response.context["opening_weekdays"], [0, 1, 2, 3, 4]
        )

    def test_create_closures_from_selected_days(self):
        days = self._past_open_days(3)
        response = self.client.post(
            reverse(
                "visitor_tracking:heatmap_create_closures",
                args=[self.year],
            ),
            data=json.dumps(
                {
                    "dates": [day.isoformat() for day in days],
                    "kind": "annual",
                    "label": "Fermeture test",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["created"], 1)
        covered = set()
        for closure in Closure.objects.filter(user=self.user):
            current = closure.start_date
            while current <= closure.end_date:
                covered.add(current)
                current += timedelta(days=1)
        self.assertTrue(set(days).issubset(covered))

    def test_create_closures_skips_pointed_days(self):
        day = self._past_open_days(1)[0]
        VisitorCount.objects.create(
            location=self.location, date=day, count=3
        )
        response = self.client.post(
            reverse(
                "visitor_tracking:heatmap_create_closures",
                args=[self.year],
            ),
            data=json.dumps(
                {
                    "dates": [day.isoformat()],
                    "kind": "annual",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Closure.objects.filter(user=self.user).exists()
        )

    def test_create_closures_rejects_old_year(self):
        response = self.client.post(
            reverse(
                "visitor_tracking:heatmap_create_closures",
                args=[2025],
            ),
            data=json.dumps(
                {"dates": ["2025-08-01"], "kind": "annual"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_closure_splits_range(self):
        closure = Closure.objects.create(
            user=self.user,
            start_date=date(self.year, 1, 5),
            end_date=date(self.year, 1, 9),
            kind="annual",
        )
        response = self.client.post(
            reverse(
                "visitor_tracking:heatmap_delete_closure",
                args=[self.year, closure.id],
            ),
            data=json.dumps({"date": date(self.year, 1, 7).isoformat()}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        closures = list(
            Closure.objects.filter(user=self.user).order_by("start_date")
        )
        self.assertEqual(len(closures), 2)
        self.assertEqual(closures[0].start_date, date(self.year, 1, 5))
        self.assertEqual(closures[0].end_date, date(self.year, 1, 6))
        self.assertEqual(closures[1].start_date, date(self.year, 1, 8))
        self.assertEqual(closures[1].end_date, date(self.year, 1, 9))

    def test_member_cannot_delete_other_closure(self):
        other = User.objects.create_user(
            username="autre", password="pass"
        )
        closure = Closure.objects.create(
            user=other,
            start_date=date(self.year, 1, 5),
            end_date=date(self.year, 1, 5),
            kind="annual",
        )
        response = self.client.post(
            reverse(
                "visitor_tracking:heatmap_delete_closure",
                args=[self.year, closure.id],
            ),
            data=json.dumps({"date": date(self.year, 1, 5).isoformat()}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_superadmin_requires_and_accepts_commune(self):
        superuser = User.objects.create_superuser(
            username="admin", password="pass"
        )
        superuser.groups.add(self.group)
        self.client.login(username="admin", password="pass")
        day = self._past_open_days(1)[0]
        payload = json.dumps(
            {"dates": [day.isoformat()], "kind": "annual"}
        )
        url = reverse(
            "visitor_tracking:heatmap_create_closures",
            args=[self.year],
        )
        response = self.client.post(
            url, data=payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            url + "?commune=mediat",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Closure.objects.filter(
                user=self.user, start_date=day
            ).exists()
        )


@override_settings(VISITOR_REPORT_V2_FROM_YEAR=2026)
class AnnualReportClosureTests(TestCase):
    """Le rapport annuel exclut les jours non ouverts."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="mediat", password="pass"
        )
        self.location = Location.objects.create(
            name="Médiathèque",
            user=self.user,
            is_active=True,
            order=1,
        )
        VisitorCount.objects.create(
            location=self.location, date=date(2026, 1, 5), count=10
        )
        VisitorCount.objects.create(
            location=self.location, date=date(2026, 1, 6), count=20
        )
        VisitorCount.objects.create(
            location=self.location, date=date(2026, 1, 11), count=5
        )
        self.today = date(2026, 11, 23)

    def build(self, year=2026):
        return AnnualReportService(
            year, self.user, today=self.today
        ).build()

    def test_closure_without_pointage_reduces_missing_days(self):
        before = self.build()
        Closure.objects.create(
            user=self.user,
            start_date=date(2026, 1, 7),
            end_date=date(2026, 1, 8),
            kind="annual",
            label="Fermeture annuelle",
        )
        after = self.build()
        self.assertEqual(
            after["totals"]["expected_days"],
            before["totals"]["expected_days"] - 2,
        )
        self.assertEqual(
            after["totals"]["missing_days"],
            before["totals"]["missing_days"] - 2,
        )
        self.assertEqual(after["totals"]["closure_days"], 2)
        self.assertEqual(
            after["monthly"][0]["closure_days"], 2
        )
        self.assertEqual(after["closure_rows"][0]["days"], 2)

    def test_pointage_on_closure_is_exceptional(self):
        Closure.objects.create(
            user=self.user,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 6),
            kind="annual",
        )
        report = self.build()
        totals = report["totals"]
        self.assertEqual(totals["total"], 35)
        self.assertEqual(totals["closure_pointed_days"], 2)
        self.assertEqual(totals["closure_pointed_total"], 30)
        self.assertEqual(totals["exceptional_days"], 3)
        self.assertEqual(totals["exceptional_total"], 35)
        self.assertEqual(totals["open_pointed_days"], 0)
        self.assertEqual(totals["avg_per_open_day"], 0)

    def test_opening_weekdays_remove_mondays(self):
        before = self.build()
        LibraryProfile.objects.create(
            user=self.user,
            name="Médiathèque",
            opening_weekdays=[1, 2, 3, 4, 5],
        )
        after = self.build()
        self.assertLess(
            after["totals"]["expected_days"],
            before["totals"]["expected_days"],
        )
        self.assertEqual(
            [item["name"] for item in after["weekday"]],
            ["Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"],
        )

    def test_legacy_report_keeps_historical_method(self):
        Closure.objects.create(
            user=self.user,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 15),
            kind="annual",
        )
        report = self.build(year=2025)
        self.assertIsNone(report["totals"]["expected_days"])
        self.assertIsNone(report["totals"]["completeness"])
        self.assertEqual(report["totals"]["total"], 0)


@override_settings(VISITOR_REPORT_V2_FROM_YEAR=2026)
class StatisticsClosureTests(TestCase):
    """La page statistiques utilise les jours d'ouverture."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(
            username="mediat", password="pass"
        )
        self.user.groups.add(self.group)
        self.location = Location.objects.create(
            name="Médiathèque",
            user=self.user,
            is_active=True,
            order=1,
        )
        self.today = timezone.now().date()
        for offset in range(10):
            VisitorCount.objects.create(
                location=self.location,
                date=self.today - timedelta(days=offset),
                count=10,
            )
        self.client.login(username="mediat", password="pass")

    def test_closure_reduces_open_days(self):
        day = self.today - timedelta(days=1)
        while day.weekday() == 6:
            day -= timedelta(days=1)
        Closure.objects.create(
            user=self.user,
            start_date=day,
            end_date=day,
            kind="annual",
        )
        response = self.client.get(
            "/mediatheque/visiteurs/statistics/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["closure_days"], 1)
        self.assertLess(
            response.context["open_days"],
            response.context["period_length"],
        )
        self.assertIsNotNone(response.context["completeness"])

    def test_closed_weekday_is_removed_from_weekday_list(self):
        LibraryProfile.objects.create(
            user=self.user,
            name="Médiathèque",
            opening_weekdays=[1, 2, 3, 4, 5],
        )
        response = self.client.get(
            "/mediatheque/visiteurs/statistics/"
        )
        self.assertEqual(
            response.context["opening_weekdays"], [1, 2, 3, 4, 5]
        )
        names = [
            item["name"]
            for item in response.context["weekday_avg_list"]
        ]
        self.assertNotIn("Lundi", names)


class PointageClosureTests(TestCase):
    """Pointage et saisie rétroactive sur un jour fermé."""

    def setUp(self):
        self.group = create_mediatheque_group()
        self.user = User.objects.create_user(
            username="mediat", password="pass"
        )
        self.user.groups.add(self.group)
        self.location = Location.objects.create(
            name="Médiathèque",
            user=self.user,
            is_active=True,
            order=1,
        )
        self.today = timezone.now().date()
        Closure.objects.create(
            user=self.user,
            start_date=self.today,
            end_date=self.today,
            kind="annual",
            label="Fermeture test",
        )
        self.client.login(username="mediat", password="pass")

    def test_index_shows_closed_banner(self):
        response = self.client.get("/mediatheque/visiteurs/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["today_is_closed"])
        self.assertContains(response, "Médiathèque fermée aujourd")

    def test_increment_is_blocked(self):
        response = self.client.post(
            reverse(
                "visitor_tracking:increment",
                args=[self.location.id],
            )
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()["closed"])
        self.assertFalse(
            VisitorCount.objects.filter(
                location=self.location, date=self.today
            ).exists()
        )

    def test_entry_form_requires_confirmation(self):
        url = reverse("visitor_tracking:entry_form")
        payload = {
            "date": self.today.isoformat(),
            f"location_{self.location.id}": "5",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jour de fermeture")
        self.assertFalse(
            VisitorCount.objects.filter(
                location=self.location, date=self.today
            ).exists()
        )

        payload["confirm_closed"] = "1"
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            VisitorCount.objects.filter(
                location=self.location, date=self.today, count=5
            ).exists()
        )
