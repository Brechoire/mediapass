"""
Services pour les calculs de statistiques des ateliers
"""

from collections import OrderedDict
from calendar import monthrange
from datetime import date, timedelta

from django.db.models import Case, Count, IntegerField, Q, Avg, Min, Max, F, Sum, When
from django.db.models.functions import Coalesce, TruncMonth, TruncWeek
from django.utils import timezone
from .models import Workshop, WorkshopParticipant
from .utils import filter_owned

DAYS_FR = {
    0: "Lundi",
    1: "Mardi",
    2: "Mercredi",
    3: "Jeudi",
    4: "Vendredi",
    5: "Samedi",
    6: "Dimanche",
}

MONTHS_FR = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


class NewsletterService:
    """Service pour préparer les données de la newsletter superadmin"""

    @staticmethod
    def _get_next_month_dates(from_date=None):
        if from_date is None:
            from_date = timezone.now().date()
        year = from_date.year
        month = from_date.month
        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1
        start = date(next_year, next_month, 1)
        _, last_day = monthrange(next_year, next_month)
        end = date(next_year, next_month, last_day)
        return start, end

    @staticmethod
    def format_date(workshop):
        """Formate la date pour la newsletter.
        - Atelier simple: 'Samedi 30 mai, 14h'
        - Atelier multi-jours: 'Du 9 au 27 juin'
        """
        start = workshop.start_date
        if workshop.end_date and workshop.end_date != start:
            start_day = start.day
            end_day = workshop.end_date.day
            end_month = MONTHS_FR[workshop.end_date.month]
            if start.month != workshop.end_date.month:
                start_month = MONTHS_FR[start.month]
                return f"Du {start_day} {start_month} au {end_day} {end_month}"
            return f"Du {start_day} au {end_day} {end_month}"

        day_name = DAYS_FR[start.weekday()]
        day = start.day
        month = MONTHS_FR[start.month]
        hour = workshop.start_time.hour
        minute = workshop.start_time.minute
        if minute == 0:
            return f"{day_name} {day} {month}, {hour}h"
        return f"{day_name} {day} {month}, {hour}h{minute:02d}"

    @staticmethod
    def format_workshop_text(workshop):
        """Format texte complet d'un atelier pour copie"""
        date_str = NewsletterService.format_date(workshop)
        return f"{workshop.title}\n\n{workshop.description}\n\n{date_str}"

    @staticmethod
    def get_newsletter_data(override_date=None):
        """Retourne les ateliers du mois suivant groupés par utilisateur médiathèque.
        Retourne un dict avec:
        - grouped_workshops: OrderedDict[User, list[Workshop]]
        - current_month: date du jour
        - next_month: 1er jour du mois suivant
        """
        next_start, next_end = NewsletterService._get_next_month_dates(override_date)

        workshops = (
            Workshop.objects.filter(
                newsletter=True,
                start_date__gte=next_start,
                start_date__lte=next_end,
            )
            .select_related("created_by")
            .order_by("created_by__username", "start_date", "start_time")
        )

        grouped = OrderedDict()
        for w in workshops:
            user = w.created_by
            if user not in grouped:
                grouped[user] = []
            grouped[user].append(w)

        return {
            "grouped_workshops": grouped,
            "current_month": override_date or timezone.now().date(),
            "next_month": next_start,
        }


class WorkshopStatisticsService:
    """Service pour calculer les statistiques des ateliers"""

    def __init__(self, start_date, end_date, user=None):
        self.start_date = start_date
        self.end_date = end_date
        self.user = user

    def _filter_workshops(self, queryset):
        if self.user and not self.user.is_superuser:
            return queryset.filter(created_by=self.user)
        return queryset

    def _filter_participants(self, queryset):
        if self.user and not self.user.is_superuser:
            return queryset.filter(workshop__created_by=self.user)
        return queryset

    @staticmethod
    def get_period_dates_static(period):
        """Retourne les dates de début et fin selon la période (méthode statique)"""
        end_date = timezone.now().date()

        if period == "6_months":
            start_date = end_date - timedelta(days=180)
        elif period == "3_months":
            start_date = end_date - timedelta(days=90)
        elif period == "1_month":
            start_date = end_date - timedelta(days=30)
        elif period == "1_week":
            start_date = end_date - timedelta(days=7)
        else:  # 12_months
            start_date = end_date - timedelta(days=365)

        # Pour éviter d'avoir la même date de début et de fin
        if start_date == end_date:
            start_date = end_date - timedelta(days=1)

        return start_date, end_date

    def get_period_dates(self, period):
        """Retourne les dates de début et fin selon la période"""
        return self.get_period_dates_static(period)

    def get_general_statistics(self):
        """Calcule les statistiques générales (1+1 requêtes au lieu de 6)"""
        workshop_stats = self._filter_workshops(
            Workshop.objects.filter(start_date__gte=self.start_date)
        ).aggregate(
            total=Count("id"),
            past=Count("id", filter=Q(start_date__lt=timezone.now().date())),
            upcoming=Count("id", filter=Q(start_date__gte=timezone.now().date())),
            cancelled=Count("id", filter=Q(status="cancelled")),
        )

        participant_stats = self._filter_participants(
            WorkshopParticipant.objects.filter(
                workshop__start_date__gte=self.start_date
            )
        ).aggregate(
            total=Count("id"),
            confirmed=Count("id", filter=Q(status="confirmed")),
            waiting=Count("id", filter=Q(status="waiting")),
        )

        return {
            "total_workshops": workshop_stats["total"],
            "total_participants": participant_stats["total"],
            "past_workshops": workshop_stats["past"],
            "upcoming_workshops": workshop_stats["upcoming"],
            "cancelled_workshops": workshop_stats["cancelled"],
            "confirmed_participants": participant_stats["confirmed"],
            "waiting_participants": participant_stats["waiting"],
        }

    def get_fill_rate_statistics(self):
        """Calcule les statistiques de taux de remplissage (1 requête au lieu de N)"""
        fill_rates = self._filter_workshops(
            Workshop.objects.filter(start_date__gte=self.start_date)
        ).aggregate(
            total_capacity=Coalesce(Sum("max_participants"), 0),
            total_confirmed=Coalesce(
                Count("participants", filter=Q(participants__status="confirmed")), 0
            ),
        )
        avg_fill_rate = (
            (fill_rates["total_confirmed"] / fill_rates["total_capacity"] * 100)
            if fill_rates["total_capacity"] > 0
            else 0
        )

        workshops_with_participants = (
            self._filter_workshops(
                Workshop.objects.filter(start_date__gte=self.start_date)
            )
            .annotate(
                confirmed_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                )
            )
            .filter(confirmed_count__gt=0)
        )

        return {
            "avg_fill_rate": round(avg_fill_rate, 1),
            "workshops_with_participants": workshops_with_participants,
        }

    def get_popular_workshops(self, limit=10):
        """Retourne les ateliers les plus populaires"""
        return (
            self._filter_workshops(
                Workshop.objects.filter(start_date__gte=self.start_date)
            )
            .annotate(
                participant_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                )
            )
            .order_by("-participant_count")[:limit]
        )

    def get_least_popular_workshops(self, limit=10):
        """Retourne les ateliers avec le moins d'inscriptions"""
        return (
            self._filter_workshops(
                Workshop.objects.filter(start_date__gte=self.start_date)
            )
            .annotate(
                participant_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                )
            )
            .order_by("participant_count")[:limit]
        )

    def get_monthly_data(self):
        """Retourne les données mensuelles"""
        return (
            self._filter_workshops(
                Workshop.objects.filter(start_date__gte=self.start_date)
            )
            .annotate(month=TruncMonth("start_date"))
            .values("month")
            .annotate(
                workshop_count=Count("id"),
                participant_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                ),
            )
            .order_by("month")
        )

    def get_yearly_data(self):
        """Retourne les données annuelles"""
        from django.db.models.functions import ExtractYear

        return (
            self._filter_workshops(
                Workshop.objects.filter(start_date__gte=self.start_date)
            )
            .annotate(year=ExtractYear("start_date"))
            .values("year")
            .annotate(
                workshop_count=Count("id"),
                participant_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                ),
            )
            .order_by("year")
        )

    def get_weekly_data(self):
        """Retourne les données hebdomadaires"""
        return (
            self._filter_workshops(
                Workshop.objects.filter(start_date__gte=self.start_date)
            )
            .annotate(week=TruncWeek("start_date"))
            .values("week")
            .annotate(
                workshop_count=Count("id"),
                participant_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                ),
            )
            .order_by("week")
        )

    def get_age_statistics(self):
        """Calcule les statistiques par âge (1 requête au lieu de 1+N)"""
        confirmed_participants = self._filter_participants(
            WorkshopParticipant.objects.filter(
                workshop__start_date__gte=self.start_date, status="confirmed"
            )
        )

        age_stats = confirmed_participants.aggregate(
            avg_age=Avg("age"),
            min_age=Min("age"),
            max_age=Max("age"),
            age_0_12=Count("id", filter=Q(age__gte=0, age__lte=12)),
            age_13_17=Count("id", filter=Q(age__gte=13, age__lte=17)),
            age_18_25=Count("id", filter=Q(age__gte=18, age__lte=25)),
            age_26_35=Count("id", filter=Q(age__gte=26, age__lte=35)),
            age_36_50=Count("id", filter=Q(age__gte=36, age__lte=50)),
            age_51_65=Count("id", filter=Q(age__gte=51, age__lte=65)),
            age_65_plus=Count("id", filter=Q(age__gte=66, age__lte=120)),
        )

        age_distribution = {
            "0-12": age_stats.pop("age_0_12", 0),
            "13-17": age_stats.pop("age_13_17", 0),
            "18-25": age_stats.pop("age_18_25", 0),
            "26-35": age_stats.pop("age_26_35", 0),
            "36-50": age_stats.pop("age_36_50", 0),
            "51-65": age_stats.pop("age_51_65", 0),
            "65+": age_stats.pop("age_65_plus", 0),
        }

        return {"age_stats": age_stats, "age_distribution": age_distribution}

    def get_group_statistics(self):
        """Calcule les statistiques des groupes"""
        return self._filter_participants(
            WorkshopParticipant.objects.filter(
                workshop__start_date__gte=self.start_date, is_group_leader=True
            )
        ).aggregate(total_groups=Count("id"), avg_group_size=Avg("group_size"))

    def get_location_statistics(self, limit=10):
        """Retourne les statistiques par lieu"""
        return (
            self._filter_workshops(
                Workshop.objects.filter(
                    start_date__gte=self.start_date, location__isnull=False
                )
            )
            .values("location__name")
            .annotate(
                workshop_count=Count("id"),
                participant_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                ),
            )
            .order_by("-workshop_count")[:limit]
        )

    def get_overbooking_statistics(self):
        """Calcule les statistiques de surcapacité"""
        ws_qs = self._filter_workshops(
            Workshop.objects.filter(start_date__gte=self.start_date)
        )
        overbooked = (
            ws_qs.annotate(
                confirmed_count=Count(
                    "participants", filter=Q(participants__status="confirmed")
                )
            )
            .filter(confirmed_count__gt=F("max_participants"))
            .count()
        )
        total = ws_qs.count()

        overbooking_rate = (overbooked / total * 100) if total > 0 else 0

        return {
            "overbooked_workshops": overbooked,
            "overbooking_rate": round(overbooking_rate, 1),
        }

    def get_all_statistics(self):
        """Retourne toutes les statistiques"""
        general_stats = self.get_general_statistics()
        fill_rate_stats = self.get_fill_rate_statistics()
        age_stats = self.get_age_statistics()
        group_stats = self.get_group_statistics()
        overbooking_stats = self.get_overbooking_statistics()

        return {
            **general_stats,
            **fill_rate_stats,
            "popular_workshops": self.get_popular_workshops(),
            "least_popular_workshops": self.get_least_popular_workshops(),
            "monthly_data": list(self.get_monthly_data()),
            "weekly_data": list(self.get_weekly_data()),
            "yearly_data": list(self.get_yearly_data()),
            **age_stats,
            "group_stats": group_stats,
            "popular_locations": self.get_location_statistics(),
            **overbooking_stats,
        }

    def get_cancelled_workshops(self):
        """Retourne les ateliers annulés avec motif"""
        return (
            self._filter_workshops(
                Workshop.objects.filter(
                    start_date__gte=self.start_date, status="cancelled"
                )
            )
            .select_related("location", "created_by")
            .order_by("-start_date")
        )
