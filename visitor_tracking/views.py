import csv
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, Max
from django.db.models.functions import TruncDate

from library_workshops.decorators import (
    mediatheque_member_required,
    mediatheque_member_required_json
)
from library_workshops.utils import filter_owned, filter_location_owned
from .models import Location, VisitorCount
from .forms import BulkVisitorCountForm, DateRangeForm, LocationForm


@mediatheque_member_required
def index(request):
    """Dashboard principal avec compteurs temps réel"""
    today = timezone.now().date()
    
    # Récupérer les espaces actifs de l'utilisateur avec leur comptage du jour
    locations = filter_location_owned(Location.objects.filter(is_active=True), request.user).order_by('order', 'name')
    
    location_data = []
    today_counts = filter_owned(VisitorCount.objects.filter(date=today), request.user, field='location__user')
    today_map = {v.location_id: v for v in today_counts}

    # Derniers 7 jours par espace (pour sparklines)
    seven_days_ago = today - timedelta(days=6)
    last_7_days = filter_owned(VisitorCount.objects.filter(
        date__gte=seven_days_ago, date__lte=today
    ), request.user, field='location__user').values("location_id", "date").annotate(total=Sum("count")).order_by("date")

    sparklines = {}
    for entry in last_7_days:
        sparklines.setdefault(entry["location_id"], []).append(entry["total"])

    for location in locations:
        count_obj = today_map.get(location.id)
        if count_obj:
            c = count_obj.count
            cid = count_obj.id
        else:
            c = 0
            cid = None
        location_data.append({
            "location": location,
            "count": c,
            "count_id": cid,
            "sparkline": sparklines.get(location.id, []),
        })
    
    # Statistiques du jour
    total_today = sum(item['count'] for item in location_data)
    
    # Statistiques des 7 derniers jours
    seven_days_ago = today - timedelta(days=6)
    week_total = filter_owned(VisitorCount.objects.filter(
        date__gte=seven_days_ago,
        date__lte=today,
        location__is_active=True
    ), request.user, field='location__user').aggregate(total=Sum('count'))['total'] or 0
    
    # Statistiques du mois en cours
    month_start = today.replace(day=1)
    month_total = filter_owned(VisitorCount.objects.filter(
        date__gte=month_start,
        date__lte=today,
        location__is_active=True
    ), request.user, field='location__user').aggregate(total=Sum('count'))['total'] or 0
    
    context = {
        'location_data': location_data,
        'today': today,
        'total_today': total_today,
        'week_total': week_total,
        'month_total': month_total,
        'title': 'Pointage visiteurs'
    }
    
    return render(request, "visitor_tracking/index.html", context)


@mediatheque_member_required_json
@require_POST
def increment_count(request, location_id, amount=1):
    """Incrémenter le compteur d'un espace (+N visiteurs)"""
    today = timezone.now().date()
    location = get_object_or_404(filter_location_owned(Location.objects.filter(is_active=True), request.user), id=location_id)
    
    # Limiter le montant entre 1 et 10 pour éviter les abus
    amount = max(1, min(int(amount), 10))
    
    count_obj, created = VisitorCount.objects.get_or_create(
        location=location,
        date=today,
        defaults={'count': 0, 'created_by': request.user}
    )
    
    count_obj.count += amount
    count_obj.updated_by = request.user
    count_obj.save()
    
    # Calculer le nouveau total du jour
    total_today = filter_owned(VisitorCount.objects.filter(
        date=today
    ), request.user, field='location__user').aggregate(total=Sum('count'))['total'] or 0
    
    return JsonResponse({
        'success': True,
        'count': count_obj.count,
        'total_today': total_today
    })


@mediatheque_member_required_json
@require_POST
def decrement_count(request, location_id):
    """Décrémenter le compteur d'un espace (-1)"""
    today = timezone.now().date()
    location = get_object_or_404(filter_location_owned(Location.objects.filter(is_active=True), request.user), id=location_id)
    
    count_obj, created = VisitorCount.objects.get_or_create(
        location=location,
        date=today,
        defaults={'count': 0, 'created_by': request.user}
    )
    
    if count_obj.count > 0:
        count_obj.count -= 1
        count_obj.updated_by = request.user
        count_obj.save()
    
    # Calculer le nouveau total du jour
    total_today = filter_owned(VisitorCount.objects.filter(
        date=today
    ), request.user, field='location__user').aggregate(total=Sum('count'))['total'] or 0
    
    return JsonResponse({
        'success': True,
        'count': count_obj.count,
        'total_today': total_today
    })


@mediatheque_member_required
def entry_form(request):
    """Formulaire de saisie rétroactive (par date)"""
    if request.method == 'POST':
        form = BulkVisitorCountForm(request.POST, user=request.user)
        if form.is_valid():
            date = form.cleaned_data['date']
            locations = filter_location_owned(Location.objects.filter(is_active=True), request.user)
            
            saved_count = 0
            for location in locations:
                field_name = f'location_{location.id}'
                count = form.cleaned_data.get(field_name, 0) or 0
                
                # Mettre à jour ou créer le comptage
                count_obj, created = VisitorCount.objects.update_or_create(
                    location=location,
                    date=date,
                    defaults={
                        'count': count,
                        'updated_by': request.user
                    }
                )
                if created:
                    count_obj.created_by = request.user
                    count_obj.save()
                saved_count += 1
            
            messages.success(
                request,
                f"Comptages enregistrés pour le {date.strftime('%d/%m/%Y')} "
                f"({saved_count} espaces)."
            )
            return redirect('visitor_tracking:index')
    else:
        # Pré-remplir avec les valeurs existantes si date fournie
        initial_date = request.GET.get('date')
        form = BulkVisitorCountForm(user=request.user)
        
        if initial_date:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(initial_date, '%Y-%m-%d').date()
                form.fields['date'].initial = date_obj
                
                # Charger les valeurs existantes
                existing_counts = filter_owned(VisitorCount.objects.filter(
                    date=date_obj
                ).select_related('location'), request.user, field='location__user')
                
                for count in existing_counts:
                    field_name = f'location_{count.location.id}'
                    if field_name in form.fields:
                        form.fields[field_name].initial = count.count
            except (ValueError, TypeError):
                pass
    
    context = {
        'form': form,
        'location_fields': form.get_location_fields(user=request.user),
        'title': 'Saisie des visiteurs'
    }
    
    return render(request, "visitor_tracking/entry_form.html", context)


@mediatheque_member_required
def statistics(request):
    """Page des statistiques avec graphiques"""
    form = DateRangeForm(request.GET or None)

    # Déterminer la période
    period = request.GET.get("period", "30_days")
    location_id = request.GET.get("location")

    today = timezone.now().date()

    # Calculer les dates selon la période
    if period == "7_days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif period == "30_days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == "this_month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "last_month":
        first_of_month = today.replace(day=1)
        end_date = first_of_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif period == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif period == "custom":
        sd = request.GET.get("start_date")
        ed = request.GET.get("end_date")
        if sd and ed:
            try:
                start_date = datetime.strptime(sd, "%Y-%m-%d").date()
                end_date = datetime.strptime(ed, "%Y-%m-%d").date()
            except ValueError:
                start_date = today - timedelta(days=30)
                end_date = today
        else:
            start_date = today - timedelta(days=30)
            end_date = today
    else:
        start_date = today - timedelta(days=30)
        end_date = today

    period_length = (end_date - start_date).days or 1

    # Requête de base
    qs = filter_owned(VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date), request.user, field='location__user')

    # Période précédente
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date - timedelta(days=1)
    prev_qs = filter_owned(VisitorCount.objects.filter(date__gte=prev_start, date__lte=prev_end), request.user, field='location__user')

    # Filtrer par espace
    selected_location = None
    if location_id:
        try:
            selected_location = filter_location_owned(Location.objects.all(), request.user).get(id=location_id)
            qs = qs.filter(location=selected_location)
            prev_qs = prev_qs.filter(location=selected_location)
        except Location.DoesNotExist:
            pass

    # Stats globales (1 requête)
    stats = qs.aggregate(
        total=Sum("count"),
        days_count=Count("date", distinct=True),
        max_count=Max("count"),
    )
    total_visitors = stats["total"] or 0
    days_with_data = stats["days_count"] or 0
    avg_per_day = round(total_visitors / period_length, 1) if period_length > 0 else 0

    # Meilleur et pire jour
    daily_totals = (
        qs.values("date").annotate(total=Sum("count")).order_by("-total")
    )
    best_day = daily_totals.first()
    worst_day = daily_totals.order_by("total").first()

    # Record
    record_day = best_day  # best_day is already the max total

    # Moyenne par jour de semaine
    weekday_data = (
        qs.values("date").annotate(total=Sum("count")).order_by("date")
    )
    weekday_sums = {}
    weekday_counts = {}
    for d in weekday_data:
        wd = d["date"].weekday()
        weekday_sums[wd] = weekday_sums.get(wd, 0) + d["total"]
        weekday_counts[wd] = weekday_counts.get(wd, 0) + 1

    weekday_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    weekday_avg_list = []
    max_wavg = 0
    for i in range(7):
        val = weekday_sums.get(i, 0) / weekday_counts.get(i, 1) if weekday_counts.get(i, 0) > 0 else 0
        val = round(val, 1)
        weekday_avg_list.append({"name": weekday_names[i], "avg": val})
        if val > max_wavg:
            max_wavg = val

    # Meilleur et pire jour de la semaine
    sorted_days = sorted(weekday_avg_list, key=lambda x: x["avg"], reverse=True)
    best_weekday = sorted_days[0] if sorted_days else None
    worst_weekday = sorted_days[-1] if sorted_days else None

    # Semaine vs week-end
    weekdays_total = sum(weekday_sums.get(i, 0) for i in range(5))
    weekend_total = sum(weekday_sums.get(i, 0) for i in (5, 6))
    weekdays_count = sum(weekday_counts.get(i, 0) for i in range(5))
    weekend_count = sum(weekday_counts.get(i, 0) for i in (5, 6))
    weekday_avg = round(weekdays_total / weekdays_count, 1) if weekdays_count > 0 else 0
    weekend_avg = round(weekend_total / weekend_count, 1) if weekend_count > 0 else 0
    weekend_vs_weekday_var = round(((weekday_avg - weekend_avg) / weekend_avg * 100), 1) if weekend_avg > 0 else 0

    # Comparaison période précédente
    prev_stats = prev_qs.aggregate(total=Sum("count"))
    prev_total = prev_stats["total"] or 0
    variation = (
        round(
            ((total_visitors - prev_total) / prev_total * 100) if prev_total > 0 else 100,
            1,
        )
    )

    # Top 3 espaces
    top_locations = (
        filter_owned(VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date), request.user, field='location__user')
        .values("location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("-total")[:3]
    )

    # Données journalières (graphique principal)
    daily_data = qs.values("date").annotate(total=Sum("count")).order_by("date")

    # Données journalières période précédente (comparaison)
    prev_daily_data = (
        prev_qs.values("date").annotate(total=Sum("count")).order_by("date")
    )

    # Données par espace
    by_location = (
        filter_owned(VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date), request.user, field='location__user')
        .values("location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("-total")
    )

    # Données journalières par espace (barres empilées)
    daily_by_location = (
        filter_owned(VisitorCount.objects.filter(date__gte=start_date, date__lte=end_date), request.user, field='location__user')
        .values("date", "location__name", "location__color")
        .annotate(total=Sum("count"))
        .order_by("date")
    )

    # Transformer en format stacked: { date: { loc_name: count } }
    stacked_raw = {}
    stacked_locations = []
    stacked_colors = []
    seen = set()
    for d in daily_by_location:
        date_key = d["date"].strftime("%d/%m")
        stacked_raw.setdefault(date_key, {})
        stacked_raw[date_key][d["location__name"]] = d["total"]
        if d["location__name"] not in seen:
            stacked_locations.append(d["location__name"])
            stacked_colors.append(d["location__color"])
            seen.add(d["location__name"])

    # Préparer les données Chart.js
    chart_labels = [d["date"].strftime("%d/%m") for d in daily_data]
    chart_values = [d["total"] for d in daily_data]

    # Construire les datasets pour les barres empilées
    stacked_datasets = []
    for loc_name, color in zip(stacked_locations, stacked_colors):
        data_row = []
        for label in chart_labels:
            data_row.append(stacked_raw.get(label, {}).get(loc_name, 0))
        if any(v > 0 for v in data_row):
            stacked_datasets.append({"label": loc_name, "data": data_row, "backgroundColor": color})

    # Supprimer la comparaison d'espaces (remplacée par le filtre personnalisé)
    # Courbe cumulée
    cumulative = []
    running = 0
    for v in chart_values:
        running += v
        cumulative.append(running)

    # Projection fin de mois (uniquement pour this_month)
    projection = None
    if period == "this_month":
        days_done = len(chart_values)
        month_days = (end_date - start_date).days + 1
        days_left = month_days - days_done
        daily_avg_proj = total_visitors / days_done if days_done > 0 else 0
        projection = round(total_visitors + daily_avg_proj * days_left) if days_left > 0 else total_visitors

    chart_prev_values = None
    if prev_daily_data:
        chart_prev_values = []
        prev_map = {d["date"]: d["total"] for d in prev_daily_data}
        for d in daily_data:
            offset = d["date"] - timedelta(days=period_length)
            val = prev_map.get(offset)
            chart_prev_values.append(val if val is not None else 0)

    # Plus utilisé (remplacé par la période personnalisée)
    # pie_labels/pie_values/pie_colors supprimés (barres empilées à la place)

    # Tendances
    if len(chart_values) >= 2:
        first_half = chart_values[: len(chart_values) // 2]
        second_half = chart_values[len(chart_values) // 2 :]
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        trend = "up" if avg_second > avg_first else ("down" if avg_second < avg_first else "stable")
        trend_pct = round(((avg_second - avg_first) / avg_first * 100), 1) if avg_first > 0 else 0
    else:
        trend = "stable"
        trend_pct = 0

    # Top 5 records
    top_days = daily_totals[:5]

    context = {
        "form": form,
        "start_date": start_date,
        "end_date": end_date,
        "period_length": period_length,
        "period": period,
        "selected_location": selected_location,
        "total_visitors": total_visitors,
        "avg_per_day": avg_per_day,
        "days_with_data": days_with_data,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "chart_prev_values": chart_prev_values,
        "stacked_datasets": stacked_datasets,
        "stacked_locations": stacked_locations,
        "by_location": by_location,
        "best_day": best_day,
        "worst_day": worst_day,
        "record_day": record_day,
        "weekday_avg_list": weekday_avg_list,
        "max_wavg": max_wavg,
        "best_weekday": best_weekday,
        "worst_weekday": worst_weekday,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "weekend_vs_weekday_var": weekend_vs_weekday_var,
        "cumulative": cumulative,
        "projection": projection,
        "prev_total": prev_total,
        "variation": variation,
        "top_locations": top_locations,
        "trend": trend,
        "trend_pct": trend_pct,
        "top_days": top_days,
        "title": "Statistiques visiteurs",
    }

    return render(request, "visitor_tracking/statistics.html", context)


@mediatheque_member_required
def export_csv(request):
    """Exporter les données en CSV"""
    period = request.GET.get('period', '30_days')
    location_id = request.GET.get('location')
    
    today = timezone.now().date()
    
    # Calculer les dates selon la période
    if period == '7_days':
        start_date = today - timedelta(days=7)
    elif period == 'this_month':
        start_date = today.replace(day=1)
    elif period == 'this_year':
        start_date = today.replace(month=1, day=1)
    else:
        start_date = today - timedelta(days=30)
    
    end_date = today
    
    # Requête
    queryset = filter_owned(VisitorCount.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('location'), request.user, field='location__user').order_by('date', 'location__order')
    
    if location_id:
        queryset = queryset.filter(location_id=location_id)
    
    # Créer la réponse CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="visiteurs_{start_date}_{end_date}.csv"'
    )
    
    # BOM UTF-8 pour Excel
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Date', 'Espace', 'Nombre de visiteurs'])
    
    for entry in queryset:
        writer.writerow([
            entry.date.strftime('%d/%m/%Y'),
            entry.location.name,
            entry.count
        ])
    
    return response


@mediatheque_member_required
def history(request):
    """Historique des pointages avec possibilité de modification"""
    # Filtres
    date_filter = request.GET.get('date')
    location_filter = request.GET.get('location')
    
    queryset = filter_owned(VisitorCount.objects.select_related(
        'location', 'created_by', 'updated_by'
    ), request.user, field='location__user').order_by('-date', 'location__order')
    
    if date_filter:
        from datetime import datetime
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            queryset = queryset.filter(date=date_obj)
        except ValueError:
            pass
    
    if location_filter:
        queryset = queryset.filter(location_id=location_filter)
    
    # Limiter aux 100 dernières entrées
    entries = queryset[:100]
    
    # Listes pour les filtres
    locations = filter_location_owned(Location.objects.filter(is_active=True), request.user).order_by('order', 'name')
    
    context = {
        'entries': entries,
        'locations': locations,
        'date_filter': date_filter,
        'location_filter': location_filter,
        'title': 'Historique des pointages'
    }
    
    return render(request, "visitor_tracking/history.html", context)


@mediatheque_member_required
def edit_entry(request, entry_id):
    """Modifier un pointage existant"""
    entry = get_object_or_404(filter_owned(VisitorCount.objects.all(), request.user, field='location__user'), id=entry_id)
    
    if request.method == 'POST':
        new_count = request.POST.get('count')
        try:
            new_count = int(new_count)
            if new_count >= 0:
                entry.count = new_count
                entry.updated_by = request.user
                entry.save()
                messages.success(
                    request,
                    f"Comptage modifié : {entry.location.name} - "
                    f"{entry.date.strftime('%d/%m/%Y')} = {new_count}"
                )
            else:
                messages.error(request, "Le nombre doit être positif.")
        except (ValueError, TypeError):
            messages.error(request, "Valeur invalide.")
        
        return redirect('visitor_tracking:history')
    
    context = {
        'entry': entry,
        'title': f'Modifier - {entry.location.name}'
    }
    
    return render(request, "visitor_tracking/edit_entry.html", context)


@mediatheque_member_required_json
@require_POST
def delete_entry(request, entry_id):
    """Supprimer un pointage"""
    entry = get_object_or_404(filter_owned(VisitorCount.objects.all(), request.user, field='location__user'), id=entry_id)
    entry.delete()
    
    return JsonResponse({'success': True})


@mediatheque_member_required
def add_space(request):
    """Ajouter un nouvel espace"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', 'bx-building')
        color = request.POST.get('color', '#4F46E5')
        
        if name:
            # Vérifier si l'espace existe déjà pour cet utilisateur
            if filter_location_owned(Location.objects.all(), request.user).filter(name__iexact=name).exists():
                messages.error(request, f"L'espace '{name}' existe déjà.")
            else:
                # Trouver le prochain ordre
                max_order = filter_location_owned(Location.objects.all(), request.user).aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                
                Location.objects.create(
                    name=name,
                    description=description,
                    icon=icon,
                    color=color,
                    user=request.user,
                    order=max_order + 1
                )
                messages.success(request, f"Espace '{name}' créé avec succès.")
                return redirect('visitor_tracking:index')
        else:
            messages.error(request, "Le nom de l'espace est obligatoire.")
    
    # Liste des icônes populaires
    icons = [
        ('bx-building', 'Bâtiment'),
        ('bx-book', 'Livre'),
        ('bx-book-reader', 'Lecteur'),
        ('bx-library', 'Bibliothèque'),
        ('bx-game', 'Jeu'),
        ('bx-joystick', 'Joystick'),
        ('bx-music', 'Musique'),
        ('bx-movie', 'Film'),
        ('bx-desktop', 'Ordinateur'),
        ('bx-laptop', 'Portable'),
        ('bx-user', 'Utilisateur'),
        ('bx-group', 'Groupe'),
        ('bx-child', 'Enfant'),
        ('bx-home', 'Maison'),
        ('bx-store', 'Magasin'),
        ('bx-coffee', 'Café'),
    ]
    
    colors = [
        ('#4F46E5', 'Indigo'),
        ('#7C3AED', 'Violet'),
        ('#EC4899', 'Rose'),
        ('#EF4444', 'Rouge'),
        ('#F97316', 'Orange'),
        ('#EAB308', 'Jaune'),
        ('#22C55E', 'Vert'),
        ('#14B8A6', 'Turquoise'),
        ('#06B6D4', 'Cyan'),
        ('#3B82F6', 'Bleu'),
        ('#6366F1', 'Indigo clair'),
        ('#8B5CF6', 'Violet clair'),
    ]
    
    context = {
        'icons': icons,
        'colors': colors,
        'title': 'Ajouter un espace'
    }
    
    return render(request, "visitor_tracking/add_space.html", context)


@mediatheque_member_required_json
@require_POST
def delete_space(request, location_id):
    """Supprimer un espace"""
    location = get_object_or_404(filter_location_owned(Location.objects.all(), request.user), id=location_id)
    name = location.name
    location.delete()
    
    return JsonResponse({'success': True, 'message': f"Espace '{name}' supprimé."})

