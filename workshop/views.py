"""Vues pour la gestion des ateliers.

Ce module contient l'ensemble des vues pour gérer les ateliers,
leurs lieux, et leurs affiches.
"""

import calendar
import csv
import json
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Avg, Count, ExpressionWrapper, F, Max, Min, Q, Sum, Value, Case, IntegerField, When
from django.db.models.functions import Coalesce, ExtractMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from accounts.utils import is_staff_or_superuser, group_required, is_staff_or_superuser_or_in_comm_group
from .forms import (
    LocationForm,
    WorkshopForm,
    WorkshopFilterForm,
    WorkshopPosterForm,
    WorkshopPosterValidationForm,
)
from .models import Location, Workshop
from .services import generate_random_filename
from .utils.html_to_word import save_stats_to_word

"""
Liste des fonctions et leur utilité:

1. group_required(*group_names):
    - Vérifie si l'utilisateur appartient à au moins un des groupes spécifiés
    ou s'il est superutilisateur.
    - Retourne un décorateur qui applique ce test.

2. is_staff_or_superuser_or_in_comm_group(user):
    - Vérifie si l'utilisateur est membre du personnel, superutilisateur ou
    appartient au groupe 'communication'.
    - Retourne True si l'une des conditions est remplie, False sinon.

3. is_staff_or_superuser(user):
    - Vérifie si l'utilisateur est membre du personnel ou superutilisateur.
    - Retourne True si l'une des conditions est remplie, False sinon.

4. send_custom_email(subject, recipient_list, template_name, context,
from_email=settings.DEFAULT_FROM_EMAIL):
    - Envoie un email personnalisé avec un template HTML.
    - Prend en paramètres le sujet, la liste des destinataires, le nom du
    template, le contexte et l'email de l'expéditeur.

5. location_update(request, pk):
    - Décorateur vérifiant si l'utilisateur passe le test
    is_staff_or_superuser.
    - Met à jour la localisation avec la clé primaire donnée.
    - Retourne la page HTML rendue avec le formulaire de mise à jour de la
    localisation.

6. location_delete(request, pk):
    - Supprime une localisation basée sur la clé primaire fournie.
    - Retourne une redirection vers la liste des localisations.

7. workshop_list_validate_poster_admin(request):
    - Affiche les ateliers nécessitant une validation d'affiche.
    - Permet à l'administrateur de valider ou rejeter les affiches soumises,
    avec la possibilité d'ajouter un commentaire.

8. approve_poster_valide(request, pk):
    - Permet de valider ou rejeter une affiche d'atelier.
    - Envoie un email pour avertir de la validation ou du refus de l'affiche.
    - Retourne la page HTML rendue avec le formulaire de validation de
    l'affiche.
"""


def send_custom_email(
    subject,
    recipient_list,
    template_name,
    context,
    from_email=settings.DEFAULT_FROM_EMAIL,
):
    """
    Envoie un email personnalisé avec un template HTML.

    Args:
        subject (str): Le sujet de l'email.
        recipient_list (list): Liste des destinataires de l'email.
        template_name (str): Chemin vers le template HTML de l'email.
        context (dict): Contexte à passer au template.
        from_email (str): L'adresse email de l'expéditeur.
    """
    html_message = render_to_string(template_name, context)
    plain_message = strip_tags(html_message)
    send_mail(
        subject,
        plain_message,
        from_email,
        recipient_list,
        html_message=html_message,
        fail_silently=False,
    )


@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser_or_in_comm_group)
def workshop_stats(request):
    """Affiche les statistiques des ateliers.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page des statistiques rendue ou le fichier Word.
    """
    current_year = timezone.now().year
    selected_year = int(request.GET.get("year", current_year))
    debug = request.GET.get("debug", "0") == "1"
    export_word = request.GET.get("export", "0") == "1"

    # Récupérer les années disponibles pour le filtre
    available_years = Workshop.objects.dates('date', 'year').values_list('date__year', flat=True).distinct()
    available_years = sorted(list(available_years), reverse=True)
    
    # Requête de base pour les ateliers de l'année sélectionnée
    workshops = Workshop.objects.filter(date__year=selected_year)

    # Toutes les stats en 1 seule requête (au lieu de 14)
    stats = workshops.aggregate(
        total=Count("id"),
        total_class_welcome=Count("id", filter=Q(class_welcome=True)),
        total_registered=Coalesce(Sum("number_registered"), 0),
        total_registered_class_welcome=Coalesce(
            Sum("number_registered", filter=Q(class_welcome=True)), 0
        ),
        total_attendees=Coalesce(Sum("number_attendees"), 0),
        no_class_avg_registered=Coalesce(
            Avg("number_registered", filter=Q(class_welcome=False)),
            0.0, output_field=models.FloatField()
        ),
        no_class_avg_attendees=Coalesce(
            Avg("number_attendees", filter=Q(class_welcome=False)),
            0.0, output_field=models.FloatField()
        ),
        no_class_max_registered=Coalesce(
            Max("number_registered", filter=Q(class_welcome=False)),
            0, output_field=models.IntegerField()
        ),
        no_class_min_registered=Coalesce(
            Min("number_registered", filter=Q(class_welcome=False)),
            0, output_field=models.IntegerField()
        ),
        instagram=Count("id", filter=Q(instagram=True)),
        facebook=Count("id", filter=Q(facebook=True)),
        mail=Count("id", filter=Q(mail=True)),
        portail=Count("id", filter=Q(portail=True)),
        vdn=Count("id", filter=Q(vdn=True)),
    )

    total_workshops = stats["total"]
    total_accueil_classe = stats["total_class_welcome"]
    total_workshops_except_class = total_workshops - total_accueil_classe
    total_registered = stats["total_registered"]
    total_registered_only_class_welcome = stats["total_registered_class_welcome"]
    total_registered_except_class = total_registered - total_registered_only_class_welcome
    total_attendees = stats["total_attendees"]

    attendance_rate = round((total_attendees / total_registered * 100), 1) if total_registered > 0 else 0
    avg_registered = stats["no_class_avg_registered"]
    avg_attendees = stats["no_class_avg_attendees"]
    max_registered = stats["no_class_max_registered"]
    min_registered = stats["no_class_min_registered"]

    # Statistiques par lieu
    workshops_by_location = (
        workshops.values("location__name")
        .annotate(
            count=Count("id"),
            total_registered=Coalesce(Sum("number_registered"), 0),
        )
        .order_by("-count")
    )

    # Statistiques par commune (séparant accueils de classe et ateliers classiques)
    workshops_by_commune = (
        workshops.values("location__city")
        .annotate(
            total_count=Count("id"),
            class_welcome_count=Count("id", filter=Q(class_welcome=True)),
            standard_count=Count("id", filter=Q(class_welcome=False)),
            total_registered=Coalesce(Sum("number_registered"), 0),
            class_welcome_registered=Coalesce(
                Sum("number_registered", filter=Q(class_welcome=True)), 0
            ),
            standard_registered=Coalesce(
                Sum("number_registered", filter=Q(class_welcome=False)), 0
            ),
        )
        .order_by("-total_count")
    )

    # Données détaillées pour le tableau par commune
    # + détails des ateliers par commune pour l'expansion inline
    commune_workshops = defaultdict(list)
    workshop_details = workshops.values(
        "id", "name", "date", "class_welcome", "location__city"
    ).order_by("location__city", "date")
    for w in workshop_details:
        city = w["location__city"] or "Non défini"
        commune_workshops[city].append(w)

    commune_table_data = []
    for commune in workshops_by_commune:
        city = commune["location__city"] or "Non défini"
        commune_table_data.append({
            'commune': city,
            'total_ateliers': commune['total_count'],
            'ateliers_classiques': commune['standard_count'],
            'accueils_classe': commune['class_welcome_count'],
            'total_participants': commune['total_registered'],
            'participants_classiques': commune['standard_registered'],
            'participants_accueils': commune['class_welcome_registered'],
            'workshops': commune_workshops.get(city, []),
        })

    # Top 5 des ateliers les plus fréquentés
    most_registered = workshops.exclude(class_welcome=True).order_by(
        "-number_registered"
    )[:5]
    
    # Top 5 des ateliers avec le meilleur taux de présence
    best_attendance = workshops.exclude(class_welcome=True)\
        .exclude(number_registered=0)\
        .annotate(attendance_rate=ExpressionWrapper(
            100 * F('number_attendees') / F('number_registered'),
            output_field=models.FloatField()
        ))\
        .order_by('-attendance_rate')[:5]

    # Statistiques mensuelles
    monthly_stats = (
        workshops.annotate(month=ExtractMonth("date"))
        .values("month")
        .annotate(
            count=Count("id"),
            total_registered=Coalesce(Sum("number_registered"), 0),
            total_attendees=Coalesce(Sum("number_attendees"), 0),
        )
        .order_by("month")
    )

    # Créer un dictionnaire avec tous les mois
    workshops_by_month = []
    for month in range(1, 13):
        month_data = next(
            (x for x in monthly_stats if x["month"] == month), None
        )
        if month_data:
            workshops_by_month.append({
                "month": month,
                "count": month_data["count"],
                "total_registered": month_data["total_registered"],
                "total_attendees": month_data["total_attendees"],
            })
        else:
            workshops_by_month.append(
                {"month": month, "count": 0, "total_registered": 0, "total_attendees": 0}
            )

    # Comparaison avec l'année précédente si ce n'est pas l'export Word et si l'année précédente existe
    # Mais uniquement sur la même période (du 1er janvier à la date actuelle)
    previous_year_data = None
    previous_year_data_class = None
    previous_year_data_no_class = None
    
    if not export_word and selected_year > 0:
        previous_year = selected_year - 1
        
        # Obtenir la date actuelle
        current_date = timezone.now().date()
        
        # Créer la même date pour l'année sélectionnée et l'année précédente
        end_date_current_year = date(selected_year, current_date.month, current_date.day)
        start_date_current_year = date(selected_year, 1, 1)
        
        end_date_previous_year = date(previous_year, current_date.month, current_date.day)
        start_date_previous_year = date(previous_year, 1, 1)
        
        period_str = f"(1 jan - {current_date.day} {calendar.month_name[current_date.month]})"
        
        # 1. TOUS LES ATELIERS
        # Filtrer les ateliers de l'année en cours jusqu'à la date actuelle
        current_year_workshops_to_date = workshops.filter(
            date__gte=start_date_current_year,
            date__lte=end_date_current_year
        )
        
        # Filtrer les ateliers de l'année précédente sur la même période
        previous_workshops = Workshop.objects.filter(
            date__year=previous_year,
            date__gte=start_date_previous_year,
            date__lte=end_date_previous_year
        )
        
        if previous_workshops.exists():
            # 1 seule requête pour les stats de l'année en cours à date
            cy_stats = current_year_workshops_to_date.aggregate(
                total=Count("id"),
                registered=Coalesce(Sum("number_registered"), 0),
                attendees=Coalesce(Sum("number_attendees"), 0),
            )
            total_workshops_to_date = cy_stats["total"]
            total_registered_to_date = cy_stats["registered"]
            total_attendees_to_date = cy_stats["attendees"]

            # 1 seule requête pour les stats de l'année précédente
            py_stats = previous_workshops.aggregate(
                total=Count("id"),
                registered=Coalesce(Sum("number_registered"), 0),
                attendees=Coalesce(Sum("number_attendees"), 0),
            )

            previous_year_data = {
                "year": previous_year,
                "total_workshops": py_stats["total"],
                "total_registered": py_stats["registered"],
                "total_attendees": py_stats["attendees"],
                "period": period_str,
                "type": "all"
            }
            
            # Calcul des variations en pourcentage en utilisant les totaux sur la même période
            if previous_year_data["total_workshops"] > 0:
                previous_year_data["workshops_variation"] = ((total_workshops_to_date - previous_year_data["total_workshops"]) / previous_year_data["total_workshops"]) * 100
            else:
                previous_year_data["workshops_variation"] = 100
                
            if previous_year_data["total_registered"] > 0:
                previous_year_data["registered_variation"] = ((total_registered_to_date - previous_year_data["total_registered"]) / previous_year_data["total_registered"]) * 100
            else:
                previous_year_data["registered_variation"] = 100
                
            # Ajouter les totaux à date dans les données de l'année précédente pour le contexte
            previous_year_data["total_workshops_to_date"] = total_workshops_to_date
            previous_year_data["total_registered_to_date"] = total_registered_to_date
        
        # 2. ATELIERS CLASSIQUES (HORS ACCUEIL CLASSE)
        # Filtrer les ateliers classiques de l'année en cours jusqu'à la date actuelle
        current_year_no_class_to_date = current_year_workshops_to_date.filter(class_welcome=False)
        
        # Filtrer les ateliers classiques de l'année précédente sur la même période
        previous_no_class = previous_workshops.filter(class_welcome=False)
        
        if previous_no_class.exists():
            # 1 seule requête pour les 2 stats de l'année en cours
            nc_stats = current_year_no_class_to_date.aggregate(
                total=Count("id"),
                registered=Coalesce(Sum("number_registered"), 0),
            )
            total_no_class_to_date = nc_stats["total"]
            total_registered_no_class_to_date = nc_stats["registered"]

            # 1 seule requête pour les 2 stats de l'année précédente
            pnc_stats = previous_no_class.aggregate(
                total=Count("id"),
                registered=Coalesce(Sum("number_registered"), 0),
            )

            previous_year_data_no_class = {
                "year": previous_year,
                "total_workshops": pnc_stats["total"],
                "total_registered": pnc_stats["registered"],
                "period": period_str,
                "type": "no_class"
            }
            
            # Calcul des variations en pourcentage en utilisant les totaux sur la même période
            if previous_year_data_no_class["total_workshops"] > 0:
                previous_year_data_no_class["workshops_variation"] = ((total_no_class_to_date - previous_year_data_no_class["total_workshops"]) / previous_year_data_no_class["total_workshops"]) * 100
            else:
                previous_year_data_no_class["workshops_variation"] = 100
                
            if previous_year_data_no_class["total_registered"] > 0:
                previous_year_data_no_class["registered_variation"] = ((total_registered_no_class_to_date - previous_year_data_no_class["total_registered"]) / previous_year_data_no_class["total_registered"]) * 100
            else:
                previous_year_data_no_class["registered_variation"] = 100
                
            # Ajouter les totaux à date dans les données de l'année précédente pour le contexte
            previous_year_data_no_class["total_workshops_to_date"] = total_no_class_to_date
            previous_year_data_no_class["total_registered_to_date"] = total_registered_no_class_to_date
        
        # 3. ACCUEILS DE CLASSE
        # Filtrer les accueils de classe de l'année en cours jusqu'à la date actuelle
        current_year_class_to_date = current_year_workshops_to_date.filter(class_welcome=True)
        
        # Filtrer les accueils de classe de l'année précédente sur la même période
        previous_class = previous_workshops.filter(class_welcome=True)
        
        if previous_class.exists():
            # 1 seule requête pour les 2 stats de l'année en cours
            c_stats = current_year_class_to_date.aggregate(
                total=Count("id"),
                registered=Coalesce(Sum("number_registered"), 0),
            )
            total_class_to_date = c_stats["total"]
            total_registered_class_to_date = c_stats["registered"]

            # 1 seule requête pour les 2 stats de l'année précédente
            pc_stats = previous_class.aggregate(
                total=Count("id"),
                registered=Coalesce(Sum("number_registered"), 0),
            )

            previous_year_data_class = {
                "year": previous_year,
                "total_workshops": pc_stats["total"],
                "total_registered": pc_stats["registered"],
                "period": period_str,
                "type": "class"
            }
            
            # Calcul des variations en pourcentage en utilisant les totaux sur la même période
            if previous_year_data_class["total_workshops"] > 0:
                previous_year_data_class["workshops_variation"] = ((total_class_to_date - previous_year_data_class["total_workshops"]) / previous_year_data_class["total_workshops"]) * 100
            else:
                previous_year_data_class["workshops_variation"] = 100
                
            if previous_year_data_class["total_registered"] > 0:
                previous_year_data_class["registered_variation"] = ((total_registered_class_to_date - previous_year_data_class["total_registered"]) / previous_year_data_class["total_registered"]) * 100
            else:
                previous_year_data_class["registered_variation"] = 100
                
            # Ajouter les totaux à date dans les données de l'année précédente pour le contexte
            previous_year_data_class["total_workshops_to_date"] = total_class_to_date
            previous_year_data_class["total_registered_to_date"] = total_registered_class_to_date
    
    # Préparation des données de contexte
    context = {
        "current_year": current_year,
        "selected_year": selected_year,
        "available_years": available_years,
        "debug": debug,
        "total_workshops": total_workshops,
        "total_accueil_classe": total_accueil_classe,
        "total_workshops_except_class": total_workshops_except_class,
        "total_registered": total_registered,
        "total_registered_only_class_welcome": (
            total_registered_only_class_welcome
        ),
        "total_registered_except_class": total_registered_except_class,
        "total_attendees": total_attendees,
        "attendance_rate": attendance_rate,
        "avg_registered": avg_registered,
        "avg_attendees": avg_attendees,
        "workshops_by_location": workshops_by_location,
        "workshops_by_commune": workshops_by_commune,
        "commune_table_data": commune_table_data,
        "workshops_by_month": list(workshops_by_month),
        "communication_stats": {
            "instagram": stats["instagram"],
            "facebook": stats["facebook"],
            "mail": stats["mail"],
            "portail": stats["portail"],
            "vdn": stats["vdn"],
        },
        "participation_stats": {
            "moyenne": float(avg_registered),
            "maximum": int(max_registered),
            "minimum": int(min_registered),
            "total_participants": total_registered,
            "total_ateliers": total_workshops,
            "total_accueil_classe": total_accueil_classe,
            "total_hors_accueil_classe": total_workshops_except_class,
            "total_presents": total_attendees,
        },
        "most_registered": most_registered,
        "best_attendance": best_attendance,
        "previous_year_data": previous_year_data,
    }
    
    # Ajouter les totaux à date au contexte si disponibles
    if previous_year_data and "total_workshops_to_date" in previous_year_data:
        context["total_workshops_to_date"] = previous_year_data["total_workshops_to_date"]
        context["total_registered_to_date"] = previous_year_data["total_registered_to_date"]
    
    # Ajouter les données de comparaison pour les ateliers classiques et accueils de classe
    context["previous_year_data_no_class"] = previous_year_data_no_class
    context["previous_year_data_class"] = previous_year_data_class

    # Données pour le bilan détaillé
    bilan_data = {
        'current_year': selected_year,
        'previous_year': selected_year - 1 if selected_year > 0 else None,
        'total_communes': len(commune_table_data),
        'top_communes': sorted(commune_table_data, key=lambda x: x['total_ateliers'], reverse=True)[:5],
        'communes_with_most_classics': sorted(commune_table_data, key=lambda x: x['ateliers_classiques'], reverse=True)[:3],
        'communes_with_most_accueils': sorted(commune_table_data, key=lambda x: x['accueils_classe'], reverse=True)[:3],
        'communes_with_most_participants': sorted(commune_table_data, key=lambda x: x['total_participants'], reverse=True)[:3],
        'communes_without_activities': [c for c in commune_table_data if c['total_ateliers'] == 0],
        'new_animations_this_year': [],  # À implémenter si on a des données sur les nouveaux types d'ateliers
        'mediatheque_36_impact': {
            'was_closed': selected_year >= 2024,  # Supposons que la médiathèque du 36 a fermé en 2024
            'impact_description': 'Fermeture de la médiathèque du 36' if selected_year >= 2024 else 'Médiathèque du 36 opérationnelle'
        }
    }

    # Calculer les variations par commune si on a des données de l'année précédente
    if previous_year_data:
        # Récupérer les données de l'année précédente par commune
        previous_commune_data = {}
        if selected_year > 0:
            previous_workshops = Workshop.objects.filter(date__year=selected_year-1)
            previous_commune_stats = (
                previous_workshops.values("location__city")
                .annotate(
                    total_count=Count("id"),
                    class_welcome_count=Count("id", filter=Q(class_welcome=True)),
                    standard_count=Count("id", filter=Q(class_welcome=False)),
                    total_registered=Coalesce(Sum("number_registered"), 0),
                )
                .order_by("-total_count")
            )
            
            for commune in previous_commune_stats:
                previous_commune_data[commune['location__city'] or 'Non défini'] = commune

        # Calculer les variations pour chaque commune
        for commune in commune_table_data:
            commune_name = commune['commune']
            if commune_name in previous_commune_data:
                prev_data = previous_commune_data[commune_name]
                commune['variation_ateliers'] = commune['total_ateliers'] - prev_data['total_count']
                commune['variation_participants'] = commune['total_participants'] - prev_data['total_registered']
                commune['variation_percentage'] = (
                    ((commune['total_ateliers'] - prev_data['total_count']) / prev_data['total_count'] * 100)
                    if prev_data['total_count'] > 0 else 100
                )
            else:
                commune['variation_ateliers'] = commune['total_ateliers']
                commune['variation_participants'] = commune['total_participants']
                commune['variation_percentage'] = 100  # Nouvelle commune

    context["bilan_data"] = bilan_data

    if export_word:
        # Générer le fichier Word
        doc = save_stats_to_word(
            context, f"statistiques_ateliers_{current_year}.docx"
        )

        # Préparer la réponse HTTP
        response = HttpResponse(
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            )
        )
        response["Content-Disposition"] = (
            f'attachment; filename="statistiques_ateliers_{current_year}.docx"'
        )
        doc.save(response)
        return response

    return render(request, "workshop/workshop_stats.html", context)


# Liste des ateliers
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser_or_in_comm_group)
def workshop_list(request):
    """Affiche la liste des ateliers avec filtres et pagination.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page de liste des ateliers.
    """
    current_year = timezone.now().year
    selected_year = request.GET.get("year", current_year)
    try:
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_year = current_year

    # Récupérer toutes les années disponibles
    all_years = Workshop.objects.dates("date", "year", order="DESC")
    years_list = [date.year for date in all_years]

    # Requête de base avec select_related pour éviter les N+1
    workshops = Workshop.objects.filter(
        date__year=selected_year
    ).select_related("location")

    # Appliquer les filtres supplémentaires
    filter_form = WorkshopFilterForm(request.GET)
    if filter_form.is_valid():
        cd = filter_form.cleaned_data

        if cd.get("q"):
            workshops = workshops.filter(name__icontains=cd["q"])

        if cd.get("location"):
            workshops = workshops.filter(location=cd["location"])

        if cd.get("city"):
            workshops = workshops.filter(location__city=cd["city"])

        if cd.get("date_from"):
            workshops = workshops.filter(date__gte=cd["date_from"])

        if cd.get("date_to"):
            workshops = workshops.filter(date__lte=cd["date_to"])

        if cd.get("class_welcome") == "yes":
            workshops = workshops.filter(class_welcome=True)
        elif cd.get("class_welcome") == "no":
            workshops = workshops.filter(class_welcome=False)

        if cd.get("poster_required") == "yes":
            workshops = workshops.filter(poster_required=True)
        elif cd.get("poster_required") == "no":
            workshops = workshops.filter(poster_required=False)

        if cd.get("has_image") == "yes":
            workshops = workshops.filter(image__isnull=False)
        elif cd.get("has_image") == "no":
            workshops = workshops.filter(image__isnull=True)

        if cd.get("poster_valide") == "yes":
            workshops = workshops.filter(poster_valide=True)
        elif cd.get("poster_valide") == "no":
            workshops = workshops.filter(poster_valide=False)

        if cd.get("number_registered_min") is not None:
            workshops = workshops.filter(
                number_registered__gte=cd["number_registered_min"]
            )

        if cd.get("number_registered_max") is not None:
            workshops = workshops.filter(
                number_registered__lte=cd["number_registered_max"]
            )

        if cd.get("number_attendees_min") is not None:
            workshops = workshops.filter(
                number_attendees__gte=cd["number_attendees_min"]
            )

        if cd.get("number_attendees_max") is not None:
            workshops = workshops.filter(
                number_attendees__lte=cd["number_attendees_max"]
            )

    # Annotation pour le tri de la colonne Affiche
    workshops = workshops.annotate(
        poster_sort=Case(
            When(class_welcome=True, then=Value(0)),
            When(image__isnull=False, then=Value(1)),
            When(poster_required=True, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    )

    # Tri
    sort_field = request.GET.get("sort", "-date")
    sortable_fields = {
        "name": "name",
        "poster_sort": "poster_sort",
        "location__name": "location__name",
        "date": "date",
        "number_registered": "number_registered",
        "number_attendees": "number_attendees",
    }
    if sort_field.lstrip("-") not in sortable_fields:
        sort_field = "-date"
    workshops = workshops.order_by(sort_field)

    # Pagination (20 par page)
    paginator = Paginator(workshops, 20)
    page_number = request.GET.get("page", 1)
    workshops_page = paginator.get_page(page_number)

    # URL de base sans le paramètre page (pour les liens de pagination)
    filter_params = request.GET.copy()
    if "page" in filter_params:
        del filter_params["page"]
    filter_params = filter_params.urlencode()

    # Déterminer la direction du tri pour chaque colonne
    sort_direction = {}
    for field_name in sortable_fields:
        if sort_field == field_name:
            sort_direction[field_name] = "asc"
        elif sort_field == f"-{field_name}":
            sort_direction[field_name] = "desc"
        else:
            sort_direction[field_name] = ""

    context = {
        "workshops": workshops_page,
        "filter_form": filter_form,
        "current_year": current_year,
        "selected_year": selected_year,
        "years_list": years_list,
        "page_obj": workshops_page,
        "paginator": paginator,
        "filter_params": filter_params,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
    }
    return render(request, "workshop/workshop_list.html", context)


# Ajout d'un atelier
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def workshop_create(request):
    """Crée un nouvel atelier.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page de création d'atelier ou redirection.
    """
    locations = Location.objects.all()
    locations_count = locations.count()
    domain = request.META.get("HTTP_HOST", "localhost")

    if request.method == "POST":
        form = WorkshopForm(request.POST, request.FILES)
        if form.is_valid():
            workshop = form.save()
            messages.success(request, "L'atelier a été créé avec succès.")

            # Vérifier la case à cocher et envoyer un e-mail si nécessaire
            if workshop.poster_required:
                from notifications.email_service import send_notification
                send_notification("poster_request", {"workshop": workshop})

            # Gérer l'affiche
            if request.FILES.get("image"):
                # Supprimer l'ancienne affiche si elle existe
                if workshop.image:
                    workshop.image.delete()

                # Générer un nom aléatoire pour la nouvelle affiche
                filename = generate_random_filename(
                    request.FILES["image"].name
                )

                # Enregistrer la nouvelle affiche avec le nouveau nom
                workshop.image.save(filename, request.FILES["image"])

            return redirect("workshop_list")
    else:
        form = WorkshopForm()
    return render(
        request,
        "workshop/workshop_create.html",
        {
            "form": form,
            "locations_count": locations_count,
            "locations": locations,
        },
    )


# Détail d'un atelier
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def workshop_detail(request, pk):
    """Affiche les détails d'un atelier.

    Args:
        request: La requête HTTP.
        pk: Clé primaire de l'atelier.

    Returns:
        HttpResponse: La page de détails de l'atelier.
    """
    workshop = get_object_or_404(Workshop.objects.select_related("location"), pk=pk)
    return render(
        request, "workshop/workshop_detail.html", {"workshop": workshop}
    )


# Modification d'un atelier
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def workshop_update(request, pk):
    """Mettre à jour un atelier existant.

    Args:
        request: La requête HTTP.
        pk: Clé primaire de l'atelier.

    Returns:
        HttpResponse: La page de modification ou redirection.
    """
    workshop = get_object_or_404(Workshop, pk=pk)
    locations = Location.objects.all()
    domain = request.META.get("HTTP_HOST", "localhost")
    if request.method == "POST":
        form = WorkshopForm(request.POST, request.FILES, instance=workshop)
        if form.is_valid():
            form.save()
            messages.success(
                request, "L'atelier a été mis à jour avec succès."
            )

            # Vérifier la case à cocher et envoyer un e-mail si nécessaire
            if workshop.poster_required:
                from notifications.email_service import send_notification
                send_notification("poster_request", {"workshop": workshop})

            # Gérer l'affiche
            if request.FILES.get("image"):
                # Supprimer l'ancienne affiche si elle existe
                if workshop.image:
                    workshop.image.delete()

                # Générer un nom aléatoire pour la nouvelle affiche
                filename = generate_random_filename(
                    request.FILES["image"].name
                )

                # Enregistrer la nouvelle affiche avec le nouveau nom
                workshop.image.save(filename, request.FILES["image"])

            return redirect("workshop_list")
    else:
        workshop.date = workshop.date.strftime("%Y-%m-%d")
        form = WorkshopForm(instance=workshop)
    return render(
        request,
        "workshop/workshop_update.html",
        {"form": form, "locations": locations},
    )


# Suppression d'un atelier
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
@require_POST
def workshop_delete(request, pk):
    """Supprime un atelier.

    Args:
        request: La requête HTTP.
        pk: Clé primaire de l'atelier.

    Returns:
        HttpResponse: Redirection vers la liste des ateliers.
    """
    workshop = get_object_or_404(Workshop, pk=pk)
    workshop.delete()
    return redirect("workshop_list")


# Validation de l'affiche
@login_required(login_url="login")
@group_required("communication")
def workshop_valide_poster(request, pk):
    """Traiter la validation de l'affiche d'un atelier.

    Args:
        request: La requête HTTP.
        pk: Clé primaire de l'atelier.

    Returns:
        HttpResponse: Redirection vers la liste des ateliers.
    """
    domain = request.META.get("HTTP_HOST", "localhost")
    workshop = get_object_or_404(Workshop, pk=pk)
    form = WorkshopPosterForm(instance=workshop, request=request)

    if request.method == "POST":
        form = WorkshopPosterForm(
            request.POST, request.FILES, instance=workshop, request=request
        )
        if form.is_valid():
            new_image = request.FILES.get("image")
            form.save()
            messages.success(
                request, "L'affiche a été ajoutée ou modifiée avec succès."
            )

            if new_image:
                send_email_notification(workshop, domain)

            # Vérifier les champs requis et poster_valide
            requis = ["facebook", "instagram", "mail", "portail", "vdn"]
            all_filled = all(form.cleaned_data.get(field) for field in requis)

            workshop.poster_required = not (
                workshop.poster_valide and all_filled
            )

            workshop.save()

    context = {
        "form": form,
        "workshop": workshop,
    }
    return render(request, "workshop/workshop_valide_poster.html", context)


def send_email_notification(workshop, domain):
    """
    Envoyer une notification par email.

    Envoie un email de notification à l'administrateur lorsqu'une nouvelle
    image est ajoutée ou modifiée.
    """
    from notifications.email_service import send_notification
    send_notification("poster_image_uploaded", {"workshop": workshop})


# Liste des ateliers par mois
@login_required(login_url="login")
@group_required("communication")
def workshop_month(request):
    """Lister les ateliers du mois en cours.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page des ateliers du mois.
    """
    today = date.today()
    month = calendar.month_name[today.month]
    start_date = today.replace(day=1)
    end_date = start_date + relativedelta(months=1)

    # Filtrer les ateliers du mois en cours
    workshops = Workshop.objects.filter(
        Q(date__gte=start_date),
        Q(date__lt=end_date),
    ).select_related("location").order_by("date")

    # Pagination
    paginator = Paginator(workshops, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "workshops": page_obj,
        "month": month,
        "is_paginated": page_obj.has_other_pages,
        "page_obj": page_obj,
        "paginator": paginator,
    }

    return render(request, "workshop/workshop_month.html", context)


# Liste des ateliers avec une affiche
@login_required(login_url="login")
@group_required("communication")
def workshops_with_poster(request):
    """Lister les ateliers avec affiches.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page des ateliers avec affiches.
    """
    base_qs = Workshop.objects.filter(Q(poster_required=True)).select_related("location")

    demandes = base_qs.filter(image__isnull=True).order_by('date')
    workshops = base_qs.exclude(image__isnull=True).order_by('date')

    paginator = Paginator(workshops, 20)
    page_number = request.GET.get("page")
    workshops_page = paginator.get_page(page_number)

    context = {
        "demandes": demandes,
        "workshops": workshops_page,
        "page_obj": workshops_page,
        "paginator": paginator,
    }

    return render(request, "workshop/workshops_with_poster.html", context)


# Suppression de l'image d'un atelier
@login_required(login_url="login")
@group_required("communication")
def workshop_delete_image(request, pk):
    """Supprime l'image d'un atelier.

    Args:
        request: La requête HTTP.
        pk: Clé primaire de l'atelier.

    Returns:
        HttpResponse: Redirection vers la liste des ateliers.
    """
    workshop = get_object_or_404(Workshop, pk=pk)

    if request.method == "POST":
        if workshop.image:
            workshop.image.delete()
        workshop.save()
        messages.success(request, "L'image de l'atelier a été supprimée.")
        return redirect("workshop_valide_poster", pk)
    else:
        return redirect("workshops_with_poster")


# Liste des lieux
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def location_list(request):
    """Affiche la liste des lieux.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page de liste des lieux.
    """
    locations = Location.objects.all()
    return render(
        request, "workshop/location_list.html", {"locations": locations}
    )


# Ajout d'un lieu
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def location_create(request):
    """Crée un nouveau lieu.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page de création de lieu ou redirection.
    """
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "La localisation a été créée avec succès."
            )
            return redirect("location_list")
    else:
        form = LocationForm()
    return render(request, "workshop/location_create.html", {"form": form})


# Détail d'un lieu
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def location_detail(request, pk):
    """Affiche les détails d'un lieu avec statistiques complètes.

    Args:
        request: La requête HTTP.
        pk: Clé primaire du lieu.

    Returns:
        HttpResponse: La page de détails du lieu avec statistiques.
    """
    location = get_object_or_404(Location, pk=pk)

    # Récupérer les ateliers de l'année en cours
    current_year = timezone.now().year
    selected_year = int(request.GET.get("year", current_year))
    workshops_qs = Workshop.objects.filter(
        location=location, date__year=selected_year
    )

    # Agrégations en une seule requête
    stats = workshops_qs.aggregate(
        total=Count("id"),
        registered=Coalesce(Sum("number_registered"), 0),
        attendees=Coalesce(Sum("number_attendees"), 0),
        classic=Count("id", filter=Q(class_welcome=False)),
        class_welcome=Count("id", filter=Q(class_welcome=True)),
        poster_required=Count("id", filter=Q(poster_required=True)),
        classic_registered=Coalesce(Sum("number_registered", filter=Q(class_welcome=False)), 0),
        class_welcome_registered=Coalesce(Sum("number_registered", filter=Q(class_welcome=True)), 0),
        instagram=Count("id", filter=Q(instagram=True)),
        facebook=Count("id", filter=Q(facebook=True)),
        mail=Count("id", filter=Q(mail=True)),
        portail=Count("id", filter=Q(portail=True)),
        vdn=Count("id", filter=Q(vdn=True)),
    )

    total_workshops = stats["total"]
    total_registered = stats["registered"]
    total_attendees = stats["attendees"]
    attendance_rate = round((total_attendees / total_registered * 100), 1) if total_registered > 0 else 0
    classic_count = stats["classic"]
    class_welcome_count = stats["class_welcome"]
    poster_required_count = stats["poster_required"]
    classic_registered = stats["classic_registered"]
    class_welcome_registered = stats["class_welcome_registered"]

    communication_stats = {k: stats[k] for k in ("instagram", "facebook", "mail", "portail", "vdn")}

    # Top 5 des ateliers par nombre d'inscrits
    top_workshops = workshops_qs.order_by('-number_registered')[:5]

    # Années disponibles
    available_years = list(workshops_qs.values_list("date__year", flat=True).distinct().order_by("-date__year")) or [current_year]

    # Statistiques mensuelles (1 requête au lieu de 12 filtres)
    monthly_stats = (
        workshops_qs.annotate(month=ExtractMonth("date"))
        .values("month")
        .annotate(
            count=Count("id"),
            total_registered=Coalesce(Sum("number_registered"), 0),
            total_attendees=Coalesce(Sum("number_attendees"), 0),
        )
        .order_by("month")
    )
    monthly_map = {m["month"]: m for m in monthly_stats if m["month"]}
    workshops_by_month = [
        monthly_map.get(m, {"month": m, "count": 0, "total_registered": 0, "total_attendees": 0})
        for m in range(1, 13)
    ]

    # Comparaison année précédente
    prev_workshops_qs = Workshop.objects.filter(
        location=location, date__year=selected_year - 1
    )
    prev_stats = prev_workshops_qs.aggregate(
        total=Count("id"),
        registered=Coalesce(Sum("number_registered"), 0),
        attendees=Coalesce(Sum("number_attendees"), 0),
    )

    previous_year_stats = {
        "total_workshops": prev_stats["total"],
        "total_registered": prev_stats["registered"],
        "total_attendees": prev_stats["attendees"],
    }

    variations = {}
    if prev_stats["total"] > 0:
        variations["workshops"] = round((total_workshops - prev_stats["total"]) / prev_stats["total"] * 100, 1)
    else:
        variations["workshops"] = 100 if total_workshops > 0 else 0

    if prev_stats["registered"] > 0:
        variations["registered"] = round((total_registered - prev_stats["registered"]) / prev_stats["registered"] * 100, 1)
    else:
        variations["registered"] = 100 if total_registered > 0 else 0

    # Données pour les graphiques (limité à 50 ateliers)
    workshops_for_graph = workshops_qs.order_by('-date')[:50]
    workshops_data = [
        {
            "id": w.id,
            "name": w.name,
            "date": w.date.isoformat(),
            "date_end": w.date_end.isoformat() if w.date_end else None,
            "number_registered": w.number_registered or 0,
            "number_attendees": w.number_attendees or 0,
            "class_welcome": w.class_welcome,
            "poster_required": w.poster_required,
            "image": w.image.url if w.image else None,
            "instagram": w.instagram,
            "facebook": w.facebook,
            "mail": w.mail,
            "portail": w.portail,
            "vdn": w.vdn,
        }
        for w in workshops_for_graph
    ]

    # Pagination pour la liste des ateliers
    workshops = workshops_qs.order_by('-date')
    paginator = Paginator(workshops, 20)
    page_number = request.GET.get('page')
    workshops = paginator.get_page(page_number)
    
    context = {
        "location": location,
        "workshops": workshops,
        "workshops_data": workshops_data,
        "total_workshops": total_workshops,
        "total_registered": total_registered,
        "total_attendees": total_attendees,
        "attendance_rate": attendance_rate,
        "classic_count": classic_count,
        "class_welcome_count": class_welcome_count,
        "poster_required_count": poster_required_count,
        "classic_registered": classic_registered,
        "class_welcome_registered": class_welcome_registered,
        "top_workshops": top_workshops,
        "workshops_by_month": workshops_by_month,
        "communication_stats": communication_stats,
        "previous_year_stats": previous_year_stats,
        "variations": variations,
        "current_year": current_year,
    }
    
    return render(request, "workshop/location_detail.html", context)


# Modification d'un lieu
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def location_update(request, pk):
    """Mettre à jour un lieu existant.

    Args:
        request: La requête HTTP.
        pk: Clé primaire du lieu.

    Returns:
        HttpResponse: La page de modification ou redirection.
    """
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(
                request, "La localisation a été mis à jour avec succès."
            )
            return redirect("location_list")
    else:
        form = LocationForm(instance=location)
    return render(request, "workshop/location_update.html", {"form": form})


# Suppression d'un lieu
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def location_delete(request, pk):
    """Supprime un lieu.

    Args:
        request: La requête HTTP.
        pk: Clé primaire du lieu.

    Returns:
        HttpResponse: Redirection vers la liste des lieux.
    """
    location = get_object_or_404(Location, pk=pk)
    location.delete()
    messages.success(request, "La localisation a été supprimée avec succès.")
    return redirect("location_list")


# Liste des ateliers nécessitant une validation d'affiche
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def workshop_list_validate_poster_admin(request):
    """Lister les ateliers nécessitant une validation.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: La page de validation des affiches.
    """
    workshops = Workshop.objects.filter(
        poster_required=True, poster_valide=False, image__isnull=False
    ).exclude(image="").select_related("location")
    return render(
        request,
        "workshop/workshop_validate_poster_admin.html",
        {"workshops": workshops},
    )


# Validation de l'affiche
@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def approve_poster_valide(request, pk):
    """Approuver l'affiche d'un atelier.

    Args:
        request: La requête HTTP.
        pk: Clé primaire de l'atelier.

    Returns:
        HttpResponse: Redirection vers la liste des validations.
    """
    workshop = get_object_or_404(Workshop, pk=pk)
    if request.method == "POST":
        form = WorkshopPosterValidationForm(request.POST, instance=workshop)
        if form.is_valid():
            workshop.description = form.cleaned_data[
                "description_poster_valide"
            ]
            if "approve" in request.POST:
                workshop.poster_valide = True
                workshop.description_poster_valide = None
                messages.success(
                    request, "L'affiche a été validée avec succès."
                )
                # email d'envois pour avertir que l'image est validé
                from notifications.email_service import send_notification
                send_notification("poster_validated", {"workshop": workshop})
            elif "reject" in request.POST:
                workshop.poster_valide = False
                # email d'envois pour avertir que l'image n'est pas validé
                from notifications.email_service import send_notification
                send_notification("poster_rejected", {"workshop": workshop})
                messages.info(request, "L'affiche a été refusée.")
            workshop.save()
            return redirect("workshop_validate_poster_admin")
    else:
        form = WorkshopPosterValidationForm(instance=workshop)
    return render(
        request,
        "workshop/approve_poster_valide.html",
        {"workshop": workshop, "form": form},
    )


@login_required(login_url="login")
@user_passes_test(is_staff_or_superuser)
def export_workshops_csv(request):
    """Générer un export CSV des ateliers.

    Args:
        request: La requête HTTP.

    Returns:
        HttpResponse: Fichier CSV des ateliers.
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="workshops.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Nom",
        "Affiche",
        "Lieu",
        "Date",
        "Heure début",
        "Heure fin",
        "Participant(s)",
        "Inscrit(s)",
    ])

    current_year = date.today().year
    workshops = Workshop.objects.filter(date__year=current_year).select_related("location")
    for workshop in workshops:
        writer.writerow([
            workshop.name,
            (
                workshop.class_welcome
                if workshop.class_welcome
                else (
                    workshop.image.url
                    if workshop.image
                    else (
                        "Affiche requise"
                        if workshop.poster_required
                        else "Aucune affiche requise"
                    )
                )
            ),
            workshop.location.name,
            workshop.date.strftime("%d/%m/%Y")
            + (
                " au " + workshop.date_end.strftime("%d/%m/%Y")
                if workshop.date_end
                else ""
            ),
            workshop.start_time.strftime("%H:%M"),
            workshop.end_time.strftime("%H:%M"),
            workshop.number_registered,
            workshop.number_attendees,
        ])

    return response
