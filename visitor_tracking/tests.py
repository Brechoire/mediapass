from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from .models import Location, VisitorCount


def create_mediatheque_group():
    group, _ = Group.objects.get_or_create(name="mediatheque")
    return group


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
