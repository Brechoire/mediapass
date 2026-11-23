"""Calculs du rapport annuel de fréquentation.

Ce module centralise le périmètre, les règles de comptage et les agrégats
du rapport annuel. Il est utilisé par l'écran, l'impression et les exports.
"""

from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Max, Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone

from .models import Location, VisitorCount
from .services import SuperadminStatisticsService, WEEKDAY_NAMES

MONTH_NAMES = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]

MONTH_NAMES_SHORT = [
    "Jan",
    "Fév",
    "Mar",
    "Avr",
    "Mai",
    "Juin",
    "Juil",
    "Août",
    "Sep",
    "Oct",
    "Nov",
    "Déc",
]

WEEKDAY_NAMES_FULL = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]


def _shift_year_back(value):
    """Décale une date d'un an en gérant le 29 février."""
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def _count_weekdays(start, end):
    """Nombre de lundis-samedis entre deux dates incluses."""
    if end < start:
        return 0
    total = 0
    current = start
    while current <= end:
        if current.weekday() != 6:
            total += 1
        current += timedelta(days=1)
    return total


def _pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0


def _variation(current, previous):
    if previous:
        return round((current - previous) / previous * 100, 1)
    return None


def _fmt_int(value):
    return f"{int(value):,}".replace(",", "\u00a0")


def _fmt_num(value):
    return f"{float(value):.1f}".replace(".", ",")


def _format_date_fr(value):
    return (
        f"{WEEKDAY_NAMES_FULL[value.weekday()]} {value.day} "
        f"{MONTH_NAMES[value.month - 1].lower()} {value.year}"
    )


def _week_windows(daily_map, start, end):
    """Meilleure et pire fenêtre de 7 jours consécutifs."""
    if (end - start).days + 1 < 7:
        return None, None

    values = []
    current = start
    while current <= end:
        values.append(daily_map.get(current, 0))
        current += timedelta(days=1)

    best = None
    worst = None
    for index in range(len(values) - 6):
        total = sum(values[index : index + 7])
        window = {
            "start": start + timedelta(days=index),
            "end": start + timedelta(days=index + 6),
            "total": total,
        }
        if best is None or total > best["total"]:
            best = window
        if worst is None or total < worst["total"]:
            worst = window
    return best, worst


class AnnualReportService:
    """Construit toutes les données du rapport annuel d'une médiathèque."""

    def __init__(self, year, scope_user, is_superuser=False, today=None):
        self.year = int(year)
        self.scope_user = scope_user
        self.is_superuser = is_superuser
        self.today = today or timezone.now().date()

        self.start_date = date(self.year, 1, 1)
        self.full_end_date = date(self.year, 12, 31)
        self.is_current_year = self.year == self.today.year
        self.is_future_year = self.year > self.today.year
        self.end_date = (
            min(self.full_end_date, self.today)
            if self.is_current_year
            else self.full_end_date
        )
        self.is_partial = self.is_current_year and self.end_date < self.full_end_date

        self.method_start_year = getattr(settings, "VISITOR_REPORT_V2_FROM_YEAR", 2026)
        self.method = "v2" if self.year >= self.method_start_year else "legacy"

        self.n1_year = self.year - 1
        self.n1_start = _shift_year_back(self.start_date)
        self.n1_end = _shift_year_back(self.end_date)

        self.locations = list(
            Location.objects.filter(user=scope_user).order_by("order", "name")
        )
        self.qs = VisitorCount.objects.filter(
            location__user=scope_user,
            date__gte=self.start_date,
            date__lte=self.end_date,
        )
        self.n1_qs = VisitorCount.objects.filter(
            location__user=scope_user,
            date__gte=self.n1_start,
            date__lte=self.n1_end,
        )
        self.has_data = self.qs.exists()

    @staticmethod
    def get_available_communes():
        """Médiathèques ayant au moins un espace, pour le sélecteur superadmin."""
        return list(
            User.objects.filter(locations__isnull=False).distinct().order_by("username")
        )

    def build(self):
        """Retourne le dictionnaire complet utilisé par l'écran et les exports."""
        daily_rows = list(
            self.qs.values("date").annotate(total=Sum("count")).order_by("date")
        )
        daily_map = {row["date"]: row["total"] or 0 for row in daily_rows}

        n1_daily_map = {
            row["date"]: row["total"] or 0
            for row in self.n1_qs.values("date").annotate(total=Sum("count"))
        }

        total = sum(daily_map.values())
        pointed_days = len(daily_map)
        sunday_dates = [d for d in daily_map if d.weekday() == 6]
        sunday_days = len(sunday_dates)
        sunday_total = sum(daily_map[d] for d in sunday_dates)
        weekday_total = total - sunday_total
        weekday_pointed_days = pointed_days - sunday_days

        avg_per_pointed_day = round(total / pointed_days, 1) if pointed_days else 0
        avg_per_open_day = (
            round(weekday_total / weekday_pointed_days, 1)
            if weekday_pointed_days
            else 0
        )

        expected_days = (
            _count_weekdays(self.start_date, self.end_date)
            if self.method == "v2"
            else None
        )
        missing_days = (
            max(expected_days - weekday_pointed_days, 0)
            if expected_days is not None
            else None
        )
        completeness = (
            round((expected_days - missing_days) / expected_days * 100, 1)
            if expected_days
            else None
        )
        zero_days = sum(1 for value in daily_map.values() if value == 0)

        n1_total = self.n1_qs.aggregate(total=Sum("count"))["total"] or 0
        n1_has_data = self.n1_qs.exists()
        variation = _variation(total, n1_total)
        last_update = self.qs.aggregate(last=Max("updated_at"))["last"]

        monthly = self._build_monthly(n1_total)
        quarterly = self._build_quarterly(monthly)
        weekday = self._build_weekday(daily_map, total)
        spaces = self._build_spaces(total)
        record = self._build_record(daily_rows)
        top_days = self._build_top_days(daily_rows)
        best_week, worst_week = _week_windows(daily_map, self.start_date, self.end_date)
        daily = [
            {
                "date": day,
                "iso": day.isoformat(),
                "label": day.strftime("%d/%m"),
                "total": daily_map[day],
                "n1": n1_daily_map.get(_shift_year_back(day), 0),
            }
            for day in sorted(daily_map)
        ]

        best_month = None
        if monthly:
            candidate = max(monthly, key=lambda item: item["total"])
            if candidate["total"] > 0:
                best_month = candidate

        best_weekday = None
        if weekday:
            candidate = max(weekday, key=lambda item: item["avg"])
            if candidate["avg"] > 0:
                best_weekday = candidate

        spaces_without_data = [space for space in spaces if not space["has_data"]]
        top_space = spaces[0] if spaces and spaces[0]["total"] > 0 else None

        perimetre = self._build_perimetre()
        synthese = self._build_synthese(
            total=total,
            pointed_days=pointed_days,
            avg_per_pointed_day=avg_per_pointed_day,
            n1_total=n1_total,
            variation=variation,
            expected_days=expected_days,
            missing_days=missing_days,
            sunday_days=sunday_days,
            sunday_total=sunday_total,
            top_space=top_space,
            record=record,
            best_weekday=best_weekday,
            best_month=best_month,
            perimetre=perimetre,
        )

        monthly_chart_rows = [
            item for item in monthly if not item["is_future"]
        ] or monthly
        spaces_with_data = [space for space in spaces if space["total"] > 0]

        return {
            "year": self.year,
            "scope": {
                "username": self.scope_user.username,
                "label": self.scope_user.username.capitalize(),
                "locations": [
                    {
                        "id": location.id,
                        "name": location.name,
                        "color": location.color,
                        "icon": location.icon,
                        "is_active": location.is_active,
                    }
                    for location in self.locations
                ],
                "location_count": len(self.locations),
                "is_superuser_view": self.is_superuser,
            },
            "period": {
                "start": self.start_date,
                "end": self.end_date,
                "full_end": self.full_end_date,
                "is_current_year": self.is_current_year,
                "is_future_year": self.is_future_year,
                "is_partial": self.is_partial,
                "label": (
                    f"Du {self.start_date:%d/%m/%Y} " f"au {self.end_date:%d/%m/%Y}"
                ),
                "status_label": self._status_label(),
                "method": self.method,
                "method_label": (
                    f"Méthode {self.year}"
                    if self.method == "v2"
                    else "Méthode historique"
                ),
                "method_start_year": self.method_start_year,
                "n1_year": self.n1_year,
                "n1_label": (
                    "à date comparable" if self.is_partial else "année complète"
                ),
                "n1_method_note": self._n1_method_note(n1_has_data),
            },
            "totals": {
                "total": total,
                "n1_total": n1_total,
                "n1_has_data": n1_has_data,
                "variation": variation,
                "pointed_days": pointed_days,
                "weekday_pointed_days": weekday_pointed_days,
                "expected_days": expected_days,
                "missing_days": missing_days,
                "completeness": completeness,
                "avg_per_pointed_day": avg_per_pointed_day,
                "avg_per_open_day": avg_per_open_day,
                "zero_days": zero_days,
                "sunday_days": sunday_days,
                "sunday_total": sunday_total,
                "last_update": last_update,
                "record": record,
                "best_month": best_month,
                "best_weekday": best_weekday,
            },
            "monthly": monthly,
            "quarterly": quarterly,
            "weekday": weekday,
            "spaces": spaces,
            "spaces_without_data": spaces_without_data,
            "daily": daily,
            "best_week": best_week,
            "worst_week": worst_week,
            "record": record,
            "top_days": top_days,
            "matrix": self._build_matrix(spaces),
            "synthese": synthese,
            "has_data": self.has_data,
            "charts": {
                "daily": {
                    "labels": [item["label"] for item in daily],
                    "totals": [item["total"] for item in daily],
                    "n1": [item["n1"] for item in daily],
                },
                "monthly": {
                    "labels": [item["short"] for item in monthly_chart_rows],
                    "totals": [item["total"] for item in monthly_chart_rows],
                    "n1": [item["n1"] for item in monthly_chart_rows],
                },
                "spaces": {
                    "labels": [item["name"] for item in spaces_with_data],
                    "totals": [item["total"] for item in spaces_with_data],
                    "colors": [item["color"] for item in spaces_with_data],
                },
                "weekday": {
                    "labels": [item["name"] for item in weekday],
                    "avg": [item["avg"] for item in weekday],
                },
            },
        }

    def _status_label(self):
        if self.is_future_year:
            return "Année à venir"
        if self.is_partial:
            return "Année en cours — données au " f"{self.end_date:%d/%m/%Y}"
        return "Année complète"

    def _n1_method_note(self, n1_has_data=True):
        if (
            n1_has_data
            and self.method == "v2"
            and self.n1_year < self.method_start_year
        ):
            return (
                f"N-1 ({self.n1_year}) est recalculé avec la méthode "
                f"{self.year} pour la comparaison ; le rapport publié "
                f"pour {self.n1_year} peut différer."
            )
        return ""

    def _build_perimetre(self):
        label = self.scope_user.username.capitalize()
        names = [location.name for location in self.locations]
        if not names:
            return f"{label} — aucun espace"
        if len(names) == 1:
            return f"{label} — 1 espace : {names[0]}"
        if len(names) <= 4:
            return f"{label} — {len(names)} espaces : {', '.join(names)}"
        return (
            f"{label} — {len(names)} espaces : "
            f"{', '.join(names[:4])} et {len(names) - 4} autres"
        )

    def _build_monthly(self, n1_total):
        monthly_rows = list(
            self.qs.annotate(month=ExtractMonth("date"))
            .values("month")
            .annotate(total=Sum("count"))
            .order_by("month")
        )
        month_map = {row["month"]: row["total"] or 0 for row in monthly_rows}

        n1_month_map = {}
        if n1_total:
            n1_rows = (
                self.n1_qs.annotate(month=ExtractMonth("date"))
                .values("month")
                .annotate(total=Sum("count"))
                .order_by("month")
            )
            n1_month_map = {row["month"]: row["total"] or 0 for row in n1_rows}

        total = sum(month_map.values())
        monthly = []
        running = 0
        for number, name in enumerate(MONTH_NAMES, start=1):
            current = month_map.get(number, 0)
            previous = n1_month_map.get(number, 0)
            running += current
            monthly.append(
                {
                    "number": number,
                    "month": name,
                    "short": MONTH_NAMES_SHORT[number - 1],
                    "total": current,
                    "n1": previous,
                    "variation": _variation(current, previous),
                    "share": _pct(current, total),
                    "cumulative": running,
                    "is_current": (self.is_current_year and number == self.today.month),
                    "is_future": (
                        self.is_future_year
                        or (self.is_current_year and number > self.today.month)
                    ),
                }
            )
        return monthly

    def _build_quarterly(self, monthly):
        quarters = []
        for index, name in enumerate(("T1", "T2", "T3", "T4")):
            rows = monthly[index * 3 : (index + 1) * 3]
            total = sum(row["total"] for row in rows)
            n1 = sum(row["n1"] for row in rows)
            quarters.append(
                {
                    "name": name,
                    "total": total,
                    "n1": n1,
                    "variation": _variation(total, n1),
                    "share": _pct(total, sum(row["total"] for row in monthly)),
                    "is_current": (
                        self.is_current_year and (self.today.month - 1) // 3 == index
                    ),
                }
            )
        return quarters

    def _build_weekday(self, daily_map, total):
        sums = {index: 0 for index in range(6)}
        counts = {index: 0 for index in range(6)}
        for day, value in daily_map.items():
            weekday = day.weekday()
            if weekday < 6:
                sums[weekday] += value
                counts[weekday] += 1
        return [
            {
                "name": WEEKDAY_NAMES[index],
                "total": sums[index],
                "avg": (round(sums[index] / counts[index], 1) if counts[index] else 0),
                "share": _pct(sums[index], total),
            }
            for index in range(6)
        ]

    def _build_spaces(self, total):
        by_loc_rows = list(
            self.qs.values("location_id").annotate(
                total=Sum("count"),
                days=Count("date", distinct=True),
                max_count=Max("count"),
            )
        )
        by_loc = {row["location_id"]: row for row in by_loc_rows}

        n1_by_loc = {
            row["location_id"]: row["total"] or 0
            for row in self.n1_qs.values("location_id").annotate(total=Sum("count"))
        }

        best_day_rows = list(
            self.qs.values("location_id", "date")
            .annotate(total=Sum("count"))
            .order_by("location_id", "-total", "date")
        )
        best_day = {}
        for row in best_day_rows:
            location_id = row["location_id"]
            if location_id not in best_day and (row["total"] or 0) > 0:
                best_day[location_id] = {
                    "date": row["date"],
                    "total": row["total"],
                }

        weekday_rows = list(
            self.qs.values("location_id", "date")
            .annotate(total=Sum("count"))
            .order_by("location_id", "date")
        )
        weekday_sums = {}
        weekday_counts = {}
        for row in weekday_rows:
            weekday = row["date"].weekday()
            if weekday >= 6:
                continue
            location_id = row["location_id"]
            weekday_sums.setdefault(location_id, [0] * 6)
            weekday_counts.setdefault(location_id, [0] * 6)
            weekday_sums[location_id][weekday] += row["total"] or 0
            weekday_counts[location_id][weekday] += 1

        spaces = []
        for location in self.locations:
            row = by_loc.get(location.id, {})
            location_total = row.get("total") or 0
            days = row.get("days") or 0
            n1 = n1_by_loc.get(location.id, 0)

            sums = weekday_sums.get(location.id, [0] * 6)
            counts = weekday_counts.get(location.id, [0] * 6)
            weekday_avgs = [
                {
                    "name": WEEKDAY_NAMES[index],
                    "avg": (
                        round(sums[index] / counts[index], 1) if counts[index] else 0
                    ),
                }
                for index in range(6)
            ]
            best_weekday = None
            if any(item["avg"] > 0 for item in weekday_avgs):
                best_weekday = max(weekday_avgs, key=lambda item: item["avg"])

            spaces.append(
                {
                    "id": location.id,
                    "name": location.name,
                    "color": location.color,
                    "icon": location.icon,
                    "is_active": location.is_active,
                    "total": location_total,
                    "share": _pct(location_total, total),
                    "days": days,
                    "avg": (round(location_total / days, 1) if days else 0),
                    "n1": n1,
                    "variation": _variation(location_total, n1),
                    "best_day": best_day.get(location.id),
                    "best_weekday": best_weekday,
                    "has_data": bool(row),
                }
            )

        spaces.sort(key=lambda item: (-item["total"], item["name"].lower()))
        return spaces

    def _build_record(self, daily_rows):
        if not daily_rows:
            return None
        best = max(daily_rows, key=lambda row: (row["total"], -row["date"].toordinal()))
        if not best["total"]:
            return None
        spaces = list(
            self.qs.filter(date=best["date"])
            .values("location__name")
            .annotate(total=Sum("count"))
            .order_by("-total", "location__name")
        )
        return {
            "date": best["date"],
            "total": best["total"],
            "spaces": [
                {"name": row["location__name"], "total": row["total"]} for row in spaces
            ],
        }

    def _build_top_days(self, daily_rows):
        ranked = sorted(
            daily_rows,
            key=lambda row: (-row["total"], row["date"]),
        )
        ranked = [row for row in ranked if row["total"] > 0][:10]
        if not ranked:
            return []
        dates = [row["date"] for row in ranked]
        breakdown_rows = (
            self.qs.filter(date__in=dates)
            .values("date", "location__name")
            .annotate(total=Sum("count"))
            .order_by("date", "-total", "location__name")
        )
        breakdown = {}
        for row in breakdown_rows:
            breakdown.setdefault(row["date"], []).append(
                {"name": row["location__name"], "total": row["total"]}
            )
        return [
            {
                "date": row["date"],
                "total": row["total"],
                "spaces": breakdown.get(row["date"], []),
            }
            for row in ranked
        ]

    def _build_matrix(self, spaces):
        rows = self.qs.values("location_id").annotate(
            month=ExtractMonth("date"),
            total=Sum("count"),
        )
        grid = {(row["location_id"], row["month"]): row["total"] or 0 for row in rows}
        return {
            "months": MONTH_NAMES,
            "months_short": MONTH_NAMES_SHORT,
            "rows": [
                {
                    "name": space["name"],
                    "values": [
                        grid.get((space["id"], month), 0) for month in range(1, 13)
                    ],
                    "total": space["total"],
                }
                for space in spaces
            ],
        }

    def _build_synthese(
        self,
        total,
        pointed_days,
        avg_per_pointed_day,
        n1_total,
        variation,
        expected_days,
        missing_days,
        sunday_days,
        sunday_total,
        top_space,
        record,
        best_weekday,
        best_month,
        perimetre,
    ):
        if not self.has_data:
            return {
                "perimetre": perimetre,
                "phrases": [
                    f"Aucun pointage n'a été enregistré pour "
                    f"{self.scope_user.username.capitalize()} en {self.year}."
                ],
            }

        phrases = [
            f"Du {self.start_date:%d/%m/%Y} au {self.end_date:%d/%m/%Y}, "
            f"{_fmt_int(total)} visiteurs ont été comptés sur "
            f"{_fmt_int(pointed_days)} jours pointés "
            f"({_fmt_num(avg_per_pointed_day)} par jour pointé en moyenne)."
        ]

        if self.is_partial:
            phrases.append(
                f"L'année est en cours : les données s'arrêtent au "
                f"{self.end_date:%d/%m/%Y}."
            )

        wording = SuperadminStatisticsService._variation_wording(variation)
        if wording:
            if self.is_partial:
                comparison = f"la même période en {self.n1_year}"
            else:
                comparison = f"{self.n1_year}"
            if wording == "stables":
                phrases.append(
                    f"La fréquentation est stable par rapport à " f"{comparison}."
                )
            else:
                phrases.append(
                    f"La fréquentation est {wording} par rapport à " f"{comparison}."
                )

        if n1_total:
            if self.is_partial:
                phrases.append(
                    f"À la même période en {self.n1_year}, "
                    f"{_fmt_int(n1_total)} visiteurs avaient été comptés."
                )
            else:
                phrases.append(
                    f"En {self.n1_year}, {_fmt_int(n1_total)} visiteurs "
                    f"avaient été comptés."
                )

        if top_space:
            phrases.append(
                f"L'espace le plus fréquenté est {top_space['name']} "
                f"({_fmt_int(top_space['total'])} visiteurs, "
                f"{_fmt_num(top_space['share'])} % du total)."
            )

        if record:
            phrases.append(
                f"Le meilleur jour est le {_format_date_fr(record['date'])} "
                f"avec {_fmt_int(record['total'])} visiteurs."
            )

        if best_weekday:
            phrases.append(
                f"Le {best_weekday['name'].lower()} est le jour le plus "
                f"fréquenté en moyenne "
                f"({_fmt_num(best_weekday['avg'])} visiteurs)."
            )

        if best_month:
            phrases.append(
                f"Le mois le plus actif est {best_month['month']} "
                f"({_fmt_int(best_month['total'])} visiteurs)."
            )

        if self.method == "v2":
            if missing_days:
                phrases.append(
                    f"{_fmt_int(missing_days)} jours ouvrés sans pointage "
                    f"sur {_fmt_int(expected_days)} jours attendus."
                )
            else:
                phrases.append(
                    f"Pointage complet sur les {_fmt_int(expected_days)} "
                    f"jours ouvrés de la période."
                )

        if sunday_days:
            phrases.append(
                f"{_fmt_int(sunday_days)} dimanche(s) ont été pointé(s) "
                f"({_fmt_int(sunday_total)} visiteurs) : ouvertures "
                f"exceptionnelles."
            )

        return {"perimetre": perimetre, "phrases": phrases}
