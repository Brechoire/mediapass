from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Value
from django.db.models.functions import Coalesce
from django.conf import settings
import logging
from .models import Commune, Lieu, CampagneDistribution, Distribution


logger = logging.getLogger(__name__)
from .forms import (
    CommuneForm, LieuForm, CampagneDistributionForm, SearchForm
)


def is_mediatheque_member_or_admin(user):
    """Vérifie si l'utilisateur est un super utilisateur ou un administrateur (exclut le groupe mediatheque)"""
    return (user.is_authenticated and
            (user.is_superuser or
             (user.groups.exists() and not user.groups.filter(name='mediatheque').exists())))


@login_required
def index(request):
    """Page d'accueil de la gestion des distributions"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    # Récupérer les campagnes récentes avec annotations
    campagnes = CampagneDistribution.objects.select_related(
        'created_by'
    ).annotate(
        _total_lieux=Count('distributions'),
        _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True))
    ).order_by('-created_at')[:5]
    
    # Statistiques générales
    total_campagnes = CampagneDistribution.objects.count()
    campagnes_actives = CampagneDistribution.objects.filter(status='active').count()
    total_lieux = Lieu.objects.filter(is_active=True).count()
    total_communes = Commune.objects.count()
    
    context = {
        'campagnes': campagnes,
        'total_campagnes': total_campagnes,
        'campagnes_actives': campagnes_actives,
        'total_lieux': total_lieux,
        'total_communes': total_communes,
    }
    
    return render(request, 'distribution/index.html', context)


@login_required
def campagne_list(request):
    """Liste des campagnes de distribution"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    # Formulaire de recherche
    search_form = SearchForm(request.GET)
    campagnes = CampagneDistribution.objects.select_related(
        'created_by'
    ).annotate(
        _total_lieux=Count('distributions'),
        _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True))
    ).all()
    
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        status = search_form.cleaned_data.get('status')
        commune = search_form.cleaned_data.get('commune')
        
        if search:
            campagnes = campagnes.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        if status:
            campagnes = campagnes.filter(status=status)
        
        if commune:
            campagnes = campagnes.filter(distributions__lieu__commune=commune).distinct()
    
    # Pagination
    paginator = Paginator(campagnes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
    }
    
    return render(request, 'distribution/campagne_list.html', context)


@login_required
def campagne_detail(request, pk):
    """Détail d'une campagne avec gestion des distributions"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    campagne = get_object_or_404(
        CampagneDistribution.objects.select_related('created_by').annotate(
            _total_lieux=Count('distributions'),
            _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True))
        ), pk=pk
    )
    
    # Récupérer les distributions existantes groupées par commune
    distributions = campagne.distributions.select_related('lieu__commune').order_by(
        'lieu__commune__name', 'lieu__name'
    )
    
    # Grouper par commune
    communes_data = {}
    for dist in distributions:
        commune_name = dist.lieu.commune.name
        if commune_name not in communes_data:
            communes_data[commune_name] = {
                'commune': dist.lieu.commune,
                'lieux': []
            }
        communes_data[commune_name]['lieux'].append(dist)
    
    context = {
        'campagne': campagne,
        'communes_data': communes_data,
    }
    
    return render(request, 'distribution/campagne_detail.html', context)


@login_required
def campagne_create(request):
    """Créer une nouvelle campagne"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    if request.method == 'POST':
        form = CampagneDistributionForm(request.POST)
        if form.is_valid():
            campagne = form.save(commit=False)
            campagne.created_by = request.user
            campagne.save()
            
            # Créer les distributions pour TOUS les lieux actifs
            # (non validées par défaut) en une seule requête
            lieux_actifs = Lieu.objects.filter(is_active=True)
            with transaction.atomic():
                Distribution.objects.bulk_create([
                    Distribution(
                        campagne=campagne,
                        lieu=lieu,
                        is_distributed=False  # Par défaut, non distribué
                    ) for lieu in lieux_actifs
                ])

            messages.success(
                request,
                f'Campagne "{campagne.name}" créée avec succès. '
                f'Tous les lieux de distribution sont disponibles.'
            )
            return redirect('distribution:campagne_detail', pk=campagne.pk)
    else:
        form = CampagneDistributionForm()
    
    context = {'form': form}
    return render(request, 'distribution/campagne_form.html', context)


@login_required
def campagne_edit(request, pk):
    """Modifier une campagne"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    campagne = get_object_or_404(CampagneDistribution, pk=pk)
    
    if request.method == 'POST':
        form = CampagneDistributionForm(request.POST, instance=campagne)
        if form.is_valid():
            form.save()
            messages.success(request, f'Campagne "{campagne.name}" modifiée avec succès.')
            return redirect('distribution:campagne_detail', pk=campagne.pk)
    else:
        form = CampagneDistributionForm(instance=campagne)
    
    context = {
        'form': form,
        'campagne': campagne,
    }
    return render(request, 'distribution/campagne_form.html', context)


@login_required
@require_POST
def toggle_distribution(request, pk):
    """Basculer le statut de distribution d'un lieu (AJAX)"""
    if not is_mediatheque_member_or_admin(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    
    try:
        distribution = get_object_or_404(Distribution, pk=pk)
        distribution.is_distributed = not distribution.is_distributed
        
        if distribution.is_distributed:
            distribution.distributed_by = request.user
        else:
            distribution.distributed_by = None
        
        distribution.save()
        
        distributed_by_name = (
            distribution.distributed_by.get_full_name()
            if distribution.distributed_by else ''
        )
        distributed_at_iso = (
            distribution.distributed_at.isoformat()
            if distribution.distributed_at else None
        )
        
        # Une seule requête pour les stats de progression
        campagne_stats = Distribution.objects.filter(
            campagne=distribution.campagne
        ).aggregate(
            total=Count('id'),
            distribue=Count('id', filter=Q(is_distributed=True))
        )
        total_lieux = campagne_stats['total']
        lieux_distribues = campagne_stats['distribue']
        progression = f"{lieux_distribues}/{total_lieux}"
        is_completed = lieux_distribues == total_lieux and total_lieux > 0
        
        return JsonResponse({
            'success': True,
            'is_distributed': distribution.is_distributed,
            'distributed_by': distributed_by_name,
            'distributed_at': distributed_at_iso,
            'progression': progression,
            'is_completed': is_completed
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def force_validate_distribution(request, pk):
    """Forcer la validation d'un lieu (AJAX) - ne désactive jamais"""
    if not is_mediatheque_member_or_admin(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    
    try:
        distribution = get_object_or_404(Distribution, pk=pk)
        distribution.is_distributed = True
        distribution.distributed_by = request.user
        distribution.save()
        
        distributed_by_name = (
            distribution.distributed_by.get_full_name()
            if distribution.distributed_by else ''
        )
        distributed_at_iso = (
            distribution.distributed_at.isoformat()
            if distribution.distributed_at else None
        )
        
        # Une seule requête pour les stats de progression
        campagne_stats = Distribution.objects.filter(
            campagne=distribution.campagne
        ).aggregate(
            total=Count('id'),
            distribue=Count('id', filter=Q(is_distributed=True))
        )
        total_lieux = campagne_stats['total']
        lieux_distribues = campagne_stats['distribue']
        progression = f"{lieux_distribues}/{total_lieux}"
        is_completed = lieux_distribues == total_lieux and total_lieux > 0
        
        return JsonResponse({
            'success': True,
            'is_distributed': distribution.is_distributed,
            'distributed_by': distributed_by_name,
            'distributed_at': distributed_at_iso,
            'progression': progression,
            'is_completed': is_completed
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def sync_campagne_lieux(request, pk):
    """Synchroniser les lieux d'une campagne avec tous les lieux actifs"""
    if not is_mediatheque_member_or_admin(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    
    try:
        campagne = get_object_or_404(CampagneDistribution, pk=pk)
        
        # Récupérer tous les lieux actifs
        lieux_actifs = Lieu.objects.filter(is_active=True)
        
        # Récupérer les IDs des lieux déjà liés à cette campagne (1 requête)
        existing_lieu_ids = set(
            campagne.distributions.values_list('lieu_id', flat=True)
        )
        
        # Créer les distributions manquantes en une seule requête
        distributions_to_create = [
            Distribution(campagne=campagne, lieu=lieu, is_distributed=False)
            for lieu in lieux_actifs
            if lieu.id not in existing_lieu_ids
        ]
        
        created_count = 0
        if distributions_to_create:
            with transaction.atomic():
                created_count = len(Distribution.objects.bulk_create(distributions_to_create))
        
        return JsonResponse({
            'success': True,
            'message': f'{created_count} nouveau(x) lieu(x) '
                       f'ajouté(s) à la campagne',
            'created_count': created_count
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def commune_list(request):
    """Liste des communes"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    communes = Commune.objects.annotate(
        lieux_count=Count('lieux', filter=Q(lieux__is_active=True))
    ).order_by('name')
    
    context = {'communes': communes}
    return render(request, 'distribution/commune_list.html', context)


@login_required
def commune_detail(request, pk):
    """Détail d'une commune avec ses lieux"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    commune = get_object_or_404(Commune, pk=pk)
    lieux = commune.lieux.filter(is_active=True).order_by('name')
    
    context = {
        'commune': commune,
        'lieux': lieux,
    }
    return render(request, 'distribution/commune_detail.html', context)


@login_required
def commune_create(request):
    """Créer une nouvelle commune"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    if request.method == 'POST':
        form = CommuneForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Commune créée avec succès.')
            return redirect('distribution:commune_list')
    else:
        form = CommuneForm()
    
    context = {'form': form}
    return render(request, 'distribution/commune_form.html', context)


@login_required
def lieu_create(request, commune_pk):
    """Créer un nouveau lieu dans une commune"""
    logger.debug("lieu_create called for commune %s by user %s", commune_pk, request.user)

    if not is_mediatheque_member_or_admin(request.user):
        logger.warning("Access denied for user %s on commune %s", request.user, commune_pk)
        return redirect('distribution:access_denied')

    commune = get_object_or_404(Commune, pk=commune_pk)

    if request.method == 'POST':
        logger.debug("POST data received for commune %s", commune_pk)
        form = LieuForm(request.POST)
        if form.is_valid():
            lieu = form.save(commit=False)
            lieu.commune = commune
            lieu.save()
            logger.info("Lieu created: %s in %s by %s", lieu.name, lieu.commune.name, request.user)
            messages.success(request, f'Lieu "{lieu.name}" créé avec succès.')
            return redirect('distribution:commune_detail', pk=commune.pk)
    else:
        form = LieuForm(initial={'commune': commune})
    
    context = {
        'form': form,
        'commune': commune,
    }
    return render(request, 'distribution/lieu_form.html', context)


@login_required
def statistics(request):
    """Page des statistiques"""
    if not is_mediatheque_member_or_admin(request.user):
        return redirect('distribution:access_denied')
    
    # Statistiques générales
    total_campagnes = CampagneDistribution.objects.count()
    campagnes_actives = CampagneDistribution.objects.filter(status='active').count()
    campagnes_terminees = CampagneDistribution.objects.filter(status='completed').count()
    
    total_communes = Commune.objects.count()
    total_lieux = Lieu.objects.filter(is_active=True).count()
    
    # Top des communes par nombre de lieux
    top_communes = Commune.objects.annotate(
        lieux_count=Count('lieux', filter=Q(lieux__is_active=True))
    ).order_by('-lieux_count')[:5]
    
    # Campagnes récentes
    campagnes_recentes = CampagneDistribution.objects.select_related(
        'created_by'
    ).annotate(
        _total_lieux=Count('distributions'),
        _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True))
    ).order_by('-created_at')[:5]
    
    context = {
        'total_campagnes': total_campagnes,
        'campagnes_actives': campagnes_actives,
        'campagnes_terminees': campagnes_terminees,
        'total_communes': total_communes,
        'total_lieux': total_lieux,
        'top_communes': top_communes,
        'campagnes_recentes': campagnes_recentes,
    }
    
    return render(request, 'distribution/statistics.html', context)


@login_required
def access_denied(request):
    """Page d'accès refusé"""
    return render(request, 'distribution/access_denied.html')