from datetime import date as date_type
from uuid import uuid4

from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA
from django.utils import timezone

from .models import Workshop, RecurrencePattern

WEEKDAY_MAP = {
    0: MO,
    1: TU,
    2: WE,
    3: TH,
    4: FR,
    5: SA,
}


def _build_byweekday(days_of_week):
    return [WEEKDAY_MAP[d] for d in days_of_week if d in WEEKDAY_MAP]


class RecurrenceService:

    @staticmethod
    def generate_dates(pattern: RecurrencePattern) -> list[date_type]:
        """Génère toutes les dates d'un pattern en excluant les exceptions."""
        excluded = set()
        for d in pattern.excluded_dates:
            try:
                if isinstance(d, str):
                    excluded.add(date_type.fromisoformat(d))
                elif isinstance(d, date_type):
                    excluded.add(d)
            except (ValueError, TypeError):
                pass

        # Mensuel / tous les 2 mois
        if pattern.frequency in ("monthly", "every_2_months"):
            if not pattern.month_day:
                return []
            dates = []
            step = 2 if pattern.frequency == "every_2_months" else 1
            current = pattern.period_start.replace(day=min(pattern.month_day, 28))
            while current <= pattern.period_end:
                try:
                    d = current.replace(day=pattern.month_day)
                except ValueError:
                    from calendar import monthrange

                    last = monthrange(current.year, current.month)[1]
                    d = current.replace(day=last)
                if (
                    pattern.period_start <= d <= pattern.period_end
                    and d not in excluded
                ):
                    dates.append(d)
                for _ in range(step):
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
            return dates

        # Pour daily / every_2_days : pas de byweekday
        if pattern.frequency in ("daily", "every_2_days"):
            interval = 2 if pattern.frequency == "every_2_days" else 1
            rule = rrule(
                DAILY,
                dtstart=pattern.period_start,
                until=pattern.period_end,
                interval=interval,
            )
            return [d.date() for d in rule if d.date() not in excluded]

        # Hebdomadaire : besoin des jours de la semaine
        byweekday = _build_byweekday(pattern.days_of_week)
        if not byweekday:
            return []

        interval_map = {
            "weekly": 1,
            "biweekly": 2,
            "every_3_weeks": 3,
        }
        interval = interval_map.get(pattern.frequency, 2)

        rule = rrule(
            WEEKLY,
            dtstart=pattern.period_start,
            until=pattern.period_end,
            byweekday=byweekday,
            interval=interval,
        )
        return [d.date() for d in rule if d.date() not in excluded]

    @staticmethod
    def create_workshops(
        request, pattern: RecurrencePattern, dates: list[date_type]
    ) -> list[Workshop]:
        """Crée les workshops à partir d'un pattern et des dates générées."""
        pattern.group = uuid4()
        pattern.created_by = request.user
        pattern.save()

        workshops = []
        for d in dates:
            ws = Workshop(
                title=pattern.title,
                description=pattern.description,
                start_date=d,
                start_time=pattern.start_time,
                end_time=pattern.end_time,
                location=pattern.location,
                max_participants=pattern.max_participants,
                is_all_ages=pattern.is_all_ages,
                min_age=pattern.min_age,
                max_age=pattern.max_age,
                newsletter=pattern.newsletter,
                is_class_welcome=pattern.is_class_welcome,
                created_by=request.user,
                recurrence_group=pattern,
            )
            ws.save()
            workshops.append(ws)
        return workshops

    @staticmethod
    def update_future_workshops(
        request, pattern: RecurrencePattern, new_data: dict
    ) -> list[Workshop]:
        """Met à jour les workshops futurs : supprime les non modifiés et recrée."""
        today = timezone.now().date()

        Workshop.objects.filter(
            recurrence_group=pattern,
            start_date__gte=today,
            recurrence_modified=False,
        ).delete()

        for field in [
            "title",
            "description",
            "start_time",
            "end_time",
            "location",
            "max_participants",
            "is_all_ages",
            "min_age",
            "max_age",
            "newsletter",
            "is_class_welcome",
        ]:
            if field in new_data:
                setattr(pattern, field, new_data[field])

        if "frequency" in new_data:
            pattern.frequency = new_data["frequency"]
        if "interval" in new_data:
            pattern.interval = new_data["interval"]
        if "days_of_week" in new_data:
            pattern.days_of_week = new_data["days_of_week"]
        if "period_start" in new_data:
            pattern.period_start = new_data["period_start"]
        if "period_end" in new_data:
            pattern.period_end = new_data["period_end"]
        if "excluded_dates" in new_data:
            pattern.excluded_dates = new_data["excluded_dates"]
        if "month_day" in new_data:
            pattern.month_day = new_data["month_day"]

        pattern.save()

        dates = RecurrenceService.generate_dates(pattern)
        return RecurrenceService.create_workshops(request, pattern, dates)
