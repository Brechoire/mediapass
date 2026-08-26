from collections import OrderedDict
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db.models import Sum, Count, Max, Min
from django.utils import timezone
from .models import VisitorCount

WEEKDAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]


class SuperadminStatisticsService:

    @staticmethod
    def compute_period(period, today=None, custom_start=None, custom_end=None):
        if today is None:
            today = timezone.now().date()

        periods = {
            "7_days": (today - timedelta(days=7), today),
            "30_days": (today - timedelta(days=30), today),
            "this_month": (today.replace(day=1), today),
            "this_year": (today.replace(month=1, day=1), today),
        }
        if period == "custom":
            if custom_start and custom_end:
                return custom_start, custom_end
            return (today - timedelta(days=30), today)
        if period == "last_month":
            first = today.replace(day=1)
            end = first - timedelta(days=1)
            start = end.replace(day=1)
        elif period in periods:
            start, end = periods[period]
        else:
            start, end = (today - timedelta(days=30), today)
        return start, end

    @staticmethod
    def get_global_stats(start_date, end_date, commune=None):
        """Stats globales tous lieux confondus (comme page stats existante).

        Si `commune` est fourni (username), les stats sont limitées à cette commune.
        """
        period_length = (end_date - start_date).days or 1
        qs = VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date)
        if commune:
            qs = qs.filter(location__user__username=commune)
        qs_ns = qs.exclude(date__week_day=1)

        agg = qs_ns.aggregate(
            total=Sum("count"),
            days_count=Count("date", distinct=True),
            max_count=Max("count"),
        )
        total = agg["total"] or 0
        days_with_data = agg["days_count"] or 0
        avg = round(total / period_length, 1) if period_length > 0 else 0

        daily = list(
            qs_ns.values("date").annotate(total=Sum("count")).order_by("-total")
        )
        best_day = daily[0] if daily else None
        worst_day = daily[-1] if daily else None

        # Période précédente
        prev_len = period_length
        prev_start = start_date - timedelta(days=prev_len)
        prev_end = start_date - timedelta(days=1)
        prev_qs = VisitorCount.objects.filter(date__gte=prev_start, date__lte=prev_end)
        if commune:
            prev_qs = prev_qs.filter(location__user__username=commune)
        prev_total = (
            prev_qs.exclude(date__week_day=1).aggregate(total=Sum("count"))["total"]
            or 0
        )
        variation = round(
            ((total - prev_total) / prev_total * 100) if prev_total > 0 else 100, 1
        )

        # Jour de semaine
        wd_data = list(
            qs_ns.values("date").annotate(total=Sum("count")).order_by("date")
        )
        wd_sums = {i: 0 for i in range(6)}
        wd_counts = {i: 0 for i in range(6)}
        for d in wd_data:
            wd = d["date"].weekday()
            wd_sums[wd] += d["total"]
            wd_counts[wd] += 1

        wd_avg_list = []
        max_wavg = 0
        for i in range(6):
            val = (
                round(wd_sums.get(i, 0) / wd_counts.get(i, 1), 1)
                if wd_counts.get(i, 0) > 0
                else 0
            )
            wd_avg_list.append({"name": WEEKDAY_NAMES[i], "avg": val})
            if val > max_wavg:
                max_wavg = val

        sorted_wd = sorted(wd_avg_list, key=lambda x: x["avg"], reverse=True)
        best_weekday = sorted_wd[0] if sorted_wd and sorted_wd[0]["avg"] > 0 else None
        worst_weekday = (
            sorted_wd[-1] if sorted_wd and sorted_wd[-1]["avg"] > 0 else None
        )

        weekdays_total = sum(wd_sums.get(i, 0) for i in range(5))
        weekend_total = wd_sums.get(5, 0)
        weekdays_count = sum(wd_counts.get(i, 0) for i in range(5))
        weekend_count = wd_counts.get(5, 0)
        weekday_avg = (
            round(weekdays_total / weekdays_count, 1) if weekdays_count > 0 else 0
        )
        weekend_avg = (
            round(weekend_total / weekend_count, 1) if weekend_count > 0 else 0
        )
        weekend_vs_weekday_var = (
            round(((weekday_avg - weekend_avg) / weekend_avg * 100), 1)
            if weekend_avg > 0
            else 0
        )

        # Top 5 meilleurs jours
        top_days = daily[:5]

        return {
            "total": total,
            "avg_per_day": avg,
            "days_with_data": days_with_data,
            "period_length": period_length,
            "record_day": best_day,
            "best_day": best_day,
            "worst_day": worst_day,
            "variation": variation,
            "prev_total": prev_total,
            "weekday_avg_list": wd_avg_list,
            "max_wavg": max_wavg,
            "best_weekday": best_weekday,
            "worst_weekday": worst_weekday,
            "weekday_avg": weekday_avg,
            "weekend_avg": weekend_avg,
            "weekend_vs_weekday_var": weekend_vs_weekday_var,
            "top_days": top_days,
        }

    @staticmethod
    def get_locations_comparison(start_date, end_date, commune=None):
        """Stats détaillées par médiathèque pour la comparaison."""
        period_length = (end_date - start_date).days or 1
        qs_total = VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date)
        if commune:
            qs_total = qs_total.filter(location__user__username=commune)
        qs_total = qs_total.exclude(date__week_day=1)
        grand_total = qs_total.aggregate(total=Sum("count"))["total"] or 0

        by_loc = (
            qs_total.values(
                "location",
                "location__name",
                "location__icon",
                "location__color",
                "location__user__username",
            )
            .annotate(
                total=Sum("count"),
                days_count=Count("date", distinct=True),
                max_count=Max("count"),
            )
            .order_by("-total")
        )

        # Meilleur jour par médiathèque
        max_by_loc = {}
        for loc_id, loc_date, loc_total in (
            qs_total.values("location", "date")
            .annotate(total=Sum("count"))
            .order_by("location", "-total")
            .values_list("location", "date", "total")
        ):
            if loc_id not in max_by_loc:
                max_by_loc[loc_id] = {"date": loc_date, "total": loc_total}

        # Jour de semaine par médiathèque
        wd_raw = list(
            qs_total.values("location", "date")
            .annotate(total=Sum("count"))
            .order_by("location", "date")
        )
        wd_by_loc = {}
        for row in wd_raw:
            lid = row["location"]
            if lid not in wd_by_loc:
                wd_by_loc[lid] = {}
            wd = row["date"].weekday()
            if wd not in wd_by_loc[lid]:
                wd_by_loc[lid][wd] = []
            wd_by_loc[lid][wd].append(row["total"])

        best_day_map = {}
        for row in by_loc:
            lid = row["location"]
            wd_data = wd_by_loc.get(lid, {})
            best_day_map[lid] = {}
            for i in range(6):
                vals = wd_data.get(i, [])
                best_day_map[lid][f"wd_{i}"] = {
                    "name": WEEKDAY_NAMES[i],
                    "avg": round(sum(vals) / len(vals), 1) if vals else 0,
                }

        locations = []
        for row in by_loc:
            lid = row["location"]
            total = row["total"] or 0
            days_count = row["days_count"] or 0
            max_count = row["max_count"] or 0
            avg = round(total / period_length, 1) if period_length > 0 else 0

            best_day_info = max_by_loc.get(lid, {})
            best_date = best_day_info.get("date")
            best_total = best_day_info.get("total", 0)

            wd_list = [best_day_map[lid][f"wd_{i}"] for i in range(6)]
            sorted_wd = sorted(wd_list, key=lambda x: x["avg"], reverse=True)
            best_wd_name = (
                sorted_wd[0]["name"] if sorted_wd and sorted_wd[0]["avg"] > 0 else "-"
            )

            pct = round((total / grand_total * 100), 1) if grand_total > 0 else 0

            locations.append(
                {
                    "id": lid,
                    "name": row["location__name"],
                    "icon": row["location__icon"] or "bx-building",
                    "color": row["location__color"] or "#4F46E5",
                    "user": row["location__user__username"] or "-",
                    "total": total,
                    "pct": pct,
                    "avg_per_day": avg,
                    "days_count": days_count,
                    "max_count": max_count,
                    "best_day_date": best_date,
                    "best_day_total": best_total,
                    "best_weekday": best_wd_name,
                    "weekday_avgs": wd_list,
                }
            )

        return locations, grand_total

    @staticmethod
    def get_stacked_chart_data(start_date, end_date, commune=None):
        """Données pour le graphique empilé par médiathèque."""
        daily_qs = VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date)
        if commune:
            daily_qs = daily_qs.filter(location__user__username=commune)
        daily = list(
            daily_qs.values("date", "location__name", "location__color")
            .annotate(total=Sum("count"))
            .order_by("date")
        )
        parts = {}
        loc_names = []
        loc_colors = {}
        for row in daily:
            ds = row["date"].isoformat()
            if ds not in parts:
                parts[ds] = {}
            loc = row["location__name"]
            parts[ds][loc] = row["total"]
            if loc not in loc_names:
                loc_names.append(loc)
            if loc not in loc_colors:
                loc_colors[loc] = row["location__color"]

        dates = sorted(parts.keys())
        datasets = []
        color_idx = 0
        base_colors = [
            "#4F46E5",
            "#7C3AED",
            "#EC4899",
            "#EF4444",
            "#F97316",
            "#22C55E",
            "#14B8A6",
            "#3B82F6",
        ]
        for loc in loc_names:
            c = loc_colors.get(loc, base_colors[color_idx % len(base_colors)])
            color_idx += 1
            datasets.append(
                {
                    "label": loc,
                    "data": [parts[d].get(loc, 0) for d in dates],
                    "backgroundColor": c,
                }
            )

        return {"labels": dates, "datasets": datasets}

    @staticmethod
    def get_available_users(start_date, end_date):
        """Retourne la liste des utilisateurs médiathèque ayant des données."""
        user_ids = (
            VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date)
            .values_list("location__user", flat=True)
            .distinct()
        )
        return list(User.objects.filter(id__in=user_ids).order_by("username"))

    @staticmethod
    def get_available_communes():
        """Liste des communes (utilisateurs) ayant au moins un pointage."""
        return list(
            User.objects.filter(locations__visitor_counts__isnull=False)
            .distinct()
            .order_by("username")
        )

    @staticmethod
    def _shift_year_back(d):
        try:
            return d.replace(year=d.year - 1)
        except ValueError:  # 29 février
            return d.replace(year=d.year - 1, day=28)

    @staticmethod
    def get_prev_period_daily(start_date, end_date, commune=None):
        """Totaux journaliers de la période précédente, format {date: total}."""
        period_length = (end_date - start_date).days or 1
        prev_start = start_date - timedelta(days=period_length)
        prev_end = start_date - timedelta(days=1)
        qs = VisitorCount.objects.filter(date__gte=prev_start, date__lte=prev_end)
        if commune:
            qs = qs.filter(location__user__username=commune)
        rows = qs.values("date").annotate(total=Sum("count"))
        return {row["date"]: row["total"] for row in rows}

    @staticmethod
    def get_n1_stats(start_date, end_date, commune=None):
        """Total de la même période l'année précédente (N-1)."""
        n1_start = SuperadminStatisticsService._shift_year_back(start_date)
        n1_end = SuperadminStatisticsService._shift_year_back(end_date)
        qs = VisitorCount.objects.filter(date__gte=n1_start, date__lte=n1_end)
        if commune:
            qs = qs.filter(location__user__username=commune)
        n1_total = qs.aggregate(total=Sum("count"))["total"] or 0
        return {"total": n1_total}

    @staticmethod
    def build_calendar_months(year, count_map, max_count):
        """Grille des 12 mois pour le calendrier de fréquentation.

        `count_map` : {date: total visiteurs}. Chaque cellule expose day,
        count, date et opacity (0-1) ; les cases hors mois sont None.
        """
        month_names = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ]

        months = []
        for m in range(1, 13):
            first_day = date(year, m, 1)
            if m == 12:
                last_day = date(year, 12, 31)
            else:
                last_day = date(year, m + 1, 1) - timedelta(days=1)

            # Lundi de la semaine contenant le 1er
            start = first_day - timedelta(days=first_day.weekday())
            # Samedi de la semaine contenant le dernier jour
            end = last_day + timedelta(days=5 - last_day.weekday())

            cells = []
            d = start
            while d <= end:
                if d.weekday() != 6:
                    if first_day <= d <= last_day:
                        cnt = count_map.get(d, 0)
                        opacity = cnt / max_count if max_count > 0 else 0
                        cells.append(
                            {
                                "day": d.day,
                                "count": cnt,
                                "date": d,
                                "opacity": opacity,
                            }
                        )
                    else:
                        cells.append(None)
                d += timedelta(days=1)

            weeks = [cells[i:i + 6] for i in range(0, len(cells), 6)]

            months.append({"name": month_names[m - 1], "weeks": weeks})

        return months

    @staticmethod
    def get_breakdown_by_date(start_date, end_date, commune=None, location_filter=None):
        """Répartition par commune/espace de chaque date : {date: [entrées]}.

        Les entrées avec un comptage nul sont exclues. Chaque entrée contient
        commune (username), espace et count.
        """
        qs = VisitorCount.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).exclude(count=0)
        if commune:
            qs = qs.filter(location__user__username=commune)
        if location_filter:
            qs = qs.filter(location_id=location_filter)
        rows = (
            qs.values(
                "date",
                "location__user__username",
                "location__name",
                "location__order",
            )
            .annotate(total=Sum("count"))
            .order_by(
                "date", "location__user__username", "location__order",
                "location__name",
            )
        )
        breakdown = {}
        for row in rows:
            breakdown.setdefault(row["date"], []).append(
                {
                    "commune": row["location__user__username"] or "-",
                    "espace": row["location__name"],
                    "count": row["total"],
                }
            )
        return breakdown

    @staticmethod
    def attach_tooltips(months, breakdown, show_commune):
        """Ajoute cell['details'] (texte multiligne) depuis la répartition.

        show_commune=True : « Commune - N visiteurs - Espace »
        show_commune=False : « Espace - N visiteurs »
        """
        for month in months:
            for week in month["weeks"]:
                for cell in week:
                    if not cell:
                        continue
                    entries = breakdown.get(cell["date"], [])
                    if not entries:
                        continue
                    lines = []
                    for e in entries:
                        if show_commune:
                            lines.append(
                                f"{e['commune'].capitalize()} - {e['count']} "
                                f"visiteur{'s' if e['count'] > 1 else ''} - "
                                f"{e['espace']}"
                            )
                        else:
                            lines.append(
                                f"{e['espace']} - {e['count']} "
                                f"visiteur{'s' if e['count'] > 1 else ''}"
                            )
                    cell["details"] = "\n".join(lines)

    @staticmethod
    def get_users_comparison(start_date, end_date, selected_usernames=None):
        """Stats agrégées par utilisateur médiathèque (tous ses espaces confondus).
        Retourne: (list[dict], best_user, worst_user) triés par total descendant.
        """
        period_length = (end_date - start_date).days or 1
        qs = VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date)

        if selected_usernames:
            qs = qs.filter(location__user__username__in=selected_usernames)

        base = qs.exclude(date__week_day=1)

        # Aggrégats par user
        by_user = (
            base.values("location__user", "location__user__username")
            .annotate(
                total=Sum("count"),
                days_count=Count("date", distinct=True),
                max_count=Max("count"),
            )
            .order_by("-total")
        )

        # Meilleur et pire jour par user
        daily = list(
            base.values("location__user", "date")
            .annotate(total=Sum("count"))
            .order_by("location__user", "-total")
        )
        best_day_per_user = OrderedDict()
        worst_day_per_user = OrderedDict()
        for row in daily:
            uid = row["location__user"]
            if uid not in best_day_per_user:
                best_day_per_user[uid] = {"date": row["date"], "total": row["total"]}
            if uid not in worst_day_per_user:
                worst_day_per_user[uid] = {"date": row["date"], "total": row["total"]}
            else:
                if row["total"] < worst_day_per_user[uid]["total"]:
                    worst_day_per_user[uid] = {
                        "date": row["date"],
                        "total": row["total"],
                    }

        # Jour de semaine par user
        wd_raw = list(
            base.values("location__user", "date")
            .annotate(total=Sum("count"))
            .order_by("location__user", "date")
        )
        wd_by_user = {}
        for row in wd_raw:
            uid = row["location__user"]
            if uid not in wd_by_user:
                wd_by_user[uid] = {i: [] for i in range(6)}
            wd = row["date"].weekday()
            wd_by_user[uid][wd].append(row["total"])

        users_data = []
        for row in by_user:
            uid = row["location__user"]
            username = row["location__user__username"]
            total = row["total"] or 0
            days_count = row["days_count"] or 0
            max_count = row["max_count"] or 0
            avg = round(total / period_length, 1) if period_length > 0 else 0

            wd_avgs = []
            for i in range(6):
                vals = wd_by_user.get(uid, {}).get(i, [])
                wd_avg = round(sum(vals) / len(vals), 1) if vals else 0
                wd_avgs.append({"name": WEEKDAY_NAMES[i], "avg": wd_avg})

            sorted_wd = sorted(wd_avgs, key=lambda x: x["avg"], reverse=True)
            best_wd = sorted_wd[0] if sorted_wd and sorted_wd[0]["avg"] > 0 else None
            worst_wd = sorted_wd[-1] if sorted_wd and sorted_wd[-1]["avg"] > 0 else None

            bd = best_day_per_user.get(uid, {})
            wd = worst_day_per_user.get(uid, {})

            users_data.append(
                {
                    "username": username,
                    "total": total,
                    "avg_per_day": avg,
                    "days_count": days_count,
                    "max_count": max_count,
                    "best_day": bd,
                    "worst_day": wd,
                    "best_weekday": best_wd,
                    "worst_weekday": worst_wd,
                    "weekday_avgs": wd_avgs,
                }
            )

        return users_data
