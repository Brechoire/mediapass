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
