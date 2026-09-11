from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Value, Case, When
from django.db.models.functions import Coalesce
from django.conf import settings
from django.utils import timezone
import json
import logging
from .models import (
    Commune, Lieu, CampagneDistribution, Distribution,
    CampagneLieuExclusion,
)


logger = logging.getLogger(__name__)
from .forms import (
    CommuneForm, LieuForm, CampagneDistributionForm, SearchForm
)


DISTRIBUTION_AGENT_GROUP = 'distribution'


def is_distribution_agent(user):
    """Vérifie si l'utilisateur est membre du groupe « distribution ».

    Cumulable avec d'autres groupes : seule l'appartenance au groupe
    compte, quels que soient les autres groupes de l'utilisateur.
    """
    return (
        user.is_authenticated
        and user.groups.filter(name=DISTRIBUTION_AGENT_GROUP).exists()
    )


def is_distribution_manager(user):
    """Vérifie si l'utilisateur a le plein accès à la gestion des distributions.

    Superuser uniquement, ou membre d'au moins un groupe hors
    « mediatheque » et hors « distribution ». Tout membre du groupe
    « distribution » (même cumulé avec un autre groupe) n'est jamais
    manager : pas de boutons Modifier/Supprimer, pas d'accès aux vues
    de gestion.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if is_distribution_agent(user):
        return False
    return user.groups.exclude(name='mediatheque').exists()


def can_access_distribution(user):
    """Accès restreint aux distributions : manager OU agent.

    Condition en OU additif : l'appartenance au groupe « distribution »
    ouvre l'accès restreint en plus des droits des autres groupes,
    sans jamais les retirer.
    """
    return is_distribution_manager(user) or is_distribution_agent(user)


def is_admin_excluding_mediatheque(user):
    """Alias historique : plein accès gestion (voir is_distribution_manager)."""
    return is_distribution_manager(user)


# Plafond de sécurité pour une quantité de flyers/documents par lieu.
QUANTITE_MAX = 1000000


def _quantite_annotations(prefix='distributions'):
    """Annotations _total_quantite / _quantite_distribuee pour les campagnes.

    Mêmes noms que les propriétés CampagneDistribution.total_quantite /
    quantite_distribuee : 0 requête supplémentaire dans les templates.
    """
    return {
        '_total_quantite': Coalesce(Sum(f'{prefix}__quantite'), 0),
        '_quantite_distribuee': Coalesce(
            Sum(
                f'{prefix}__quantite',
                filter=Q(**{f'{prefix}__is_distributed': True}),
            ),
            0,
        ),
    }


def _campagne_quantite_totals(campagne):
    """Totaux documents d'une campagne (1 requête aggregate)."""
    return Distribution.objects.filter(
        campagne=campagne
    ).aggregate(
        total_quantite=Coalesce(Sum('quantite'), 0),
        quantite_distribuee=Coalesce(
            Sum('quantite', filter=Q(is_distributed=True)), 0
        ),
    )


def _commune_quantite_totals(campagne, commune_id):
    """Totaux documents d'une commune dans une campagne (1 requête)."""
    return Distribution.objects.filter(
        campagne=campagne, lieu__commune_id=commune_id
    ).aggregate(
        total=Coalesce(Sum('quantite'), 0),
        distribuee=Coalesce(
            Sum('quantite', filter=Q(is_distributed=True)), 0
        ),
    )


def _all_communes_quantites(campagne):
    """Totaux documents par commune d'une campagne (1 requête).

    Retourne {commune_id: {'commune_name': ..., 'total': ..., 'distribuee': ...}}.
    """
    rows = (
        Distribution.objects.filter(campagne=campagne)
        .values('lieu__commune_id', 'lieu__commune__name')
        .annotate(
            total=Coalesce(Sum('quantite'), 0),
            distribuee=Coalesce(
                Sum('quantite', filter=Q(is_distributed=True)), 0
            ),
        )
    )
    return {
        row['lieu__commune_id']: {
            'commune_name': row['lieu__commune__name'],
            'total': row['total'],
            'distribuee': row['distribuee'],
        }
        for row in rows
    }


def _parse_quantite(value):
    """Valide une quantité saisie. Retourne (quantite, erreur)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, 'Quantité manquante'
    try:
        quantite = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        return None, 'Quantité invalide (entier attendu)'
    if isinstance(value, bool) or quantite < 0:
        return None, 'La quantité doit être un entier positif ou nul'
    if quantite > QUANTITE_MAX:
        return None, f'La quantité ne peut pas dépasser {QUANTITE_MAX}'
    return quantite, None


@login_required
def index(request):
    """Page d'accueil de la gestion des distributions"""
    if not can_access_distribution(request.user):
        return redirect('distribution:access_denied')
    if not is_distribution_manager(request.user):
        # Agents « distribution » : directement vers les campagnes en cours.
        return redirect('distribution:campagne_list')
    
    # Récupérer les campagnes récentes avec annotations
    campagnes = CampagneDistribution.objects.select_related(
        'created_by'
    ).annotate(
        _total_lieux=Count('distributions'),
        _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True)),
        **_quantite_annotations()
    ).order_by('-created_at')[:5]
    
    # Statistiques générales
    total_campagnes = CampagneDistribution.objects.count()
    campagnes_actives = CampagneDistribution.objects.filter(
        status='active', end_date__gte=timezone.localdate()
    ).count()
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
    if not can_access_distribution(request.user):
        return redirect('distribution:access_denied')

    can_manage = is_distribution_manager(request.user)
    
    # Formulaire de recherche
    search_form = SearchForm(request.GET)
    campagnes = CampagneDistribution.objects.select_related(
        'created_by'
    ).annotate(
        _total_lieux=Count('distributions'),
        _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True)),
        **_quantite_annotations()
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
        
        if status and can_manage:
            today = timezone.localdate()
            if status == 'active':
                campagnes = campagnes.filter(
                    status='active', end_date__gte=today
                )
            elif status == 'completed':
                campagnes = campagnes.filter(
                    Q(status='completed') |
                    Q(status='active', end_date__lt=today)
                )
            else:
                campagnes = campagnes.filter(status=status)
        
        if commune:
            campagnes = campagnes.filter(distributions__lieu__commune=commune).distinct()

    if not can_manage:
        # Agents « distribution » : seules les campagnes en cours,
        # quel que soit le filtre statut demandé.
        campagnes = campagnes.filter(
            status='active', end_date__gte=timezone.localdate()
        )
    
    # Tri : date de fin croissante (la plus proche en premier),
    # campagnes déjà terminées en bas de liste
    today = timezone.localdate()
    campagnes = campagnes.order_by(
        Case(
            When(end_date__lt=today, then=Value(1)),
            default=Value(0),
        ),
        'end_date',
    )

    # Pagination
    paginator = Paginator(campagnes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'can_manage': can_manage,
    }

    return render(request, 'distribution/campagne_list.html', context)


@login_required
def campagne_detail(request, pk):
    """Détail d'une campagne avec gestion des distributions"""
    if not can_access_distribution(request.user):
        return redirect('distribution:access_denied')

    can_manage = is_distribution_manager(request.user)
    
    campagne = get_object_or_404(
        CampagneDistribution.objects.select_related('created_by').annotate(
            _total_lieux=Count('distributions'),
            _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True)),
            **_quantite_annotations()
        ), pk=pk
    )

    if not can_manage and campagne.effective_status != 'active':
        # Agents « distribution » : seules les campagnes en cours.
        return redirect('distribution:access_denied')

    # Récupérer les distributions existantes groupées par commune
    distributions = campagne.distributions.select_related('lieu__commune').order_by(
        'lieu__commune__name', 'lieu__name'
    )

    # Grouper par commune avec totaux documents (0 requête sup.)
    communes_data = {}
    for dist in distributions:
        commune_name = dist.lieu.commune.name
        if commune_name not in communes_data:
            communes_data[commune_name] = {
                'commune': dist.lieu.commune,
                'lieux': [],
                'total_quantite': 0,
                'quantite_distribuee': 0,
            }
        entry = communes_data[commune_name]
        entry['lieux'].append(dist)
        entry['total_quantite'] += dist.quantite or 0
        if dist.is_distributed:
            entry['quantite_distribuee'] += dist.quantite or 0

    # Lieux retirés de cette campagne (1 requête, pour réintégration).
    lieux_exclus = campagne.lieux_exclus.select_related(
        'lieu__commune'
    ).order_by('lieu__commune__name', 'lieu__name')

    context = {
        'campagne': campagne,
        'communes_data': communes_data,
        'lieux_exclus': lieux_exclus,
        'can_manage': can_manage,
    }

    return render(request, 'distribution/campagne_detail.html', context)


@login_required
def campagne_create(request):
    """Créer une nouvelle campagne"""
    if not is_distribution_manager(request.user):
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
                        is_distributed=False,  # Par défaut, non distribué
                        quantite=0,  # Quantité à saisir lieu par lieu
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
    if not is_distribution_manager(request.user):
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
def campagne_delete(request, pk):
    """Supprimer une campagne (confirmation en GET, suppression en POST).

    Seules les lignes Distribution de cette campagne sont effacées
    (CASCADE) : les lieux, communes et autres campagnes sont conservés.
    """
    if not is_distribution_manager(request.user):
        return redirect('distribution:access_denied')

    campagne = get_object_or_404(
        CampagneDistribution.objects.select_related('created_by').annotate(
            _total_lieux=Count('distributions'),
            _lieux_distribues=Count(
                'distributions', filter=Q(distributions__is_distributed=True)
            ),
            **_quantite_annotations()
        ), pk=pk
    )

    if request.method == 'POST':
        name = campagne.name
        lieux_count = campagne.total_lieux
        campagne.delete()
        messages.success(
            request,
            f'Campagne "{name}" supprimée. '
            f'{lieux_count} lieu(x) retiré(s) de cette campagne, '
            'les lieux et communes sont conservés.'
        )
        return redirect('distribution:campagne_list')

    context = {'campagne': campagne}
    return render(request, 'distribution/campagne_confirm_delete.html', context)


@login_required
@require_POST
def toggle_distribution(request, pk):
    """Basculer le statut de distribution d'un lieu (AJAX)"""
    if not can_access_distribution(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        distribution = get_object_or_404(Distribution, pk=pk)
        if (not is_distribution_manager(request.user)
                and distribution.campagne.effective_status != 'active'):
            return JsonResponse(
                {'error': 'Campagne terminée, validation impossible'},
                status=403,
            )
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
            distribue=Count('id', filter=Q(is_distributed=True)),
            total_quantite=Coalesce(Sum('quantite'), 0),
            quantite_distribuee=Coalesce(
                Sum('quantite', filter=Q(is_distributed=True)), 0
            ),
        )
        total_lieux = campagne_stats['total']
        lieux_distribues = campagne_stats['distribue']
        progression = f"{lieux_distribues}/{total_lieux}"
        is_completed = lieux_distribues == total_lieux and total_lieux > 0

        commune_stats = _commune_quantite_totals(
            distribution.campagne, distribution.lieu.commune_id
        )

        return JsonResponse({
            'success': True,
            'is_distributed': distribution.is_distributed,
            'distributed_by': distributed_by_name,
            'distributed_at': distributed_at_iso,
            'progression': progression,
            'is_completed': is_completed,
            'total_quantite': campagne_stats['total_quantite'],
            'quantite_distribuee': campagne_stats['quantite_distribuee'],
            'commune_id': distribution.lieu.commune_id,
            'commune_total_quantite': commune_stats['total'],
            'commune_quantite_distribuee': commune_stats['distribuee'],
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def force_validate_distribution(request, pk):
    """Forcer la validation d'un lieu (AJAX) - ne désactive jamais"""
    if not can_access_distribution(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        distribution = get_object_or_404(Distribution, pk=pk)
        if (not is_distribution_manager(request.user)
                and distribution.campagne.effective_status != 'active'):
            return JsonResponse(
                {'error': 'Campagne terminée, validation impossible'},
                status=403,
            )
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
            distribue=Count('id', filter=Q(is_distributed=True)),
            total_quantite=Coalesce(Sum('quantite'), 0),
            quantite_distribuee=Coalesce(
                Sum('quantite', filter=Q(is_distributed=True)), 0
            ),
        )
        total_lieux = campagne_stats['total']
        lieux_distribues = campagne_stats['distribue']
        progression = f"{lieux_distribues}/{total_lieux}"
        is_completed = lieux_distribues == total_lieux and total_lieux > 0

        commune_stats = _commune_quantite_totals(
            distribution.campagne, distribution.lieu.commune_id
        )

        return JsonResponse({
            'success': True,
            'is_distributed': distribution.is_distributed,
            'distributed_by': distributed_by_name,
            'distributed_at': distributed_at_iso,
            'progression': progression,
            'is_completed': is_completed,
            'total_quantite': campagne_stats['total_quantite'],
            'quantite_distribuee': campagne_stats['quantite_distribuee'],
            'commune_id': distribution.lieu.commune_id,
            'commune_total_quantite': commune_stats['total'],
            'commune_quantite_distribuee': commune_stats['distribuee'],
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def bulk_update_distributions(request, pk):
    """Mise à jour groupée des distributions d'une campagne (AJAX).

    Remplace le fan-out JS (N requêtes toggle/force-validate) par :
    1 SELECT de cadrage + 1 à 2 UPDATE + 1 aggregate, en une transaction.

    Corps JSON attendu : {"ids": [1, 2, ...], "action": "validate"|"deselect"}.
    - "validate" : is_distributed=True, distributed_by=request.user,
      distributed_at conservée si déjà renseignée (logique Distribution.save()),
      posée à maintenant sinon.
    - "deselect" : is_distributed=False, distributed_by=None,
      distributed_at=None (logique Distribution.save()).
    Seules les distributions de la campagne `pk` sont touchées.
    """
    if not can_access_distribution(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        campagne = get_object_or_404(CampagneDistribution, pk=pk)
        if (not is_distribution_manager(request.user)
                and campagne.effective_status != 'active'):
            return JsonResponse(
                {'error': 'Campagne terminée, validation impossible'},
                status=403,
            )

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

        raw_ids = payload.get('ids', [])
        action = payload.get('action', 'validate')
        if action not in ('validate', 'deselect'):
            return JsonResponse({'error': 'Action invalide'}, status=400)
        if not isinstance(raw_ids, list) or not raw_ids:
            return JsonResponse(
                {'error': 'Liste ids vide ou invalide'}, status=400
            )
        if len(raw_ids) > 1000:
            return JsonResponse(
                {'error': 'Trop de distributions (max 1000)'}, status=400
            )
        try:
            ids = sorted({int(i) for i in raw_ids})
        except (TypeError, ValueError):
            return JsonResponse({'error': 'ids invalides'}, status=400)

        with transaction.atomic():
            scoped = Distribution.objects.filter(
                campagne=campagne, id__in=ids
            )
            if action == 'validate':
                now = timezone.now()
                # Ordre important : d'abord les lignes déjà datées, puis les
                # sans date. L'inverse recompterait les lignes venant d'être
                # datées (le 2e UPDATE re-matcherait le 1er).
                updated_old = scoped.filter(
                    distributed_at__isnull=False
                ).update(
                    is_distributed=True, distributed_by=request.user,
                )
                updated_new = scoped.filter(
                    distributed_at__isnull=True
                ).update(
                    is_distributed=True, distributed_by=request.user,
                    distributed_at=now,
                )
                updated_count = updated_new + updated_old
            else:
                updated_count = scoped.update(
                    is_distributed=False, distributed_by=None,
                    distributed_at=None,
                )

            campagne_stats = Distribution.objects.filter(
                campagne=campagne
            ).aggregate(
                total=Count('id'),
                distribue=Count('id', filter=Q(is_distributed=True)),
                total_quantite=Coalesce(Sum('quantite'), 0),
                quantite_distribuee=Coalesce(
                    Sum('quantite', filter=Q(is_distributed=True)), 0
                ),
            )
            communes_quantites = _all_communes_quantites(campagne)

        total_lieux = campagne_stats['total']
        lieux_distribues = campagne_stats['distribue']
        return JsonResponse({
            'success': True,
            'updated_count': updated_count,
            'total': total_lieux,
            'distribue': lieux_distribues,
            'progression': f"{lieux_distribues}/{total_lieux}",
            'is_completed': lieux_distribues == total_lieux and total_lieux > 0,
            'total_quantite': campagne_stats['total_quantite'],
            'quantite_distribuee': campagne_stats['quantite_distribuee'],
            'communes_quantites': communes_quantites,
        })

    except Exception as e:
        logger.exception("Erreur bulk_update_distributions campagne=%s", pk)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def update_distribution_quantite(request, campagne_pk, pk):
    """Mettre à jour la quantité d'une distribution (AJAX).

    Corps JSON attendu : {"quantite": <entier >= 0>}.
    Seule la distribution `pk` de la campagne `campagne_pk` est touchée.
    Réponse : nouvelle quantité + totaux campagne et commune pour MAJ temps réel.
    """
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        campagne = get_object_or_404(CampagneDistribution, pk=campagne_pk)
        distribution = get_object_or_404(
            Distribution, pk=pk, campagne=campagne
        )

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

        quantite, erreur = _parse_quantite(payload.get('quantite'))
        if erreur:
            return JsonResponse({'error': erreur}, status=400)

        distribution.quantite = quantite
        distribution.save(update_fields=['quantite', 'updated_at'])

        totaux = _campagne_quantite_totals(campagne)
        commune_stats = _commune_quantite_totals(
            campagne, distribution.lieu.commune_id
        )

        return JsonResponse({
            'success': True,
            'quantite': distribution.quantite,
            'total_quantite': totaux['total_quantite'],
            'quantite_distribuee': totaux['quantite_distribuee'],
            'commune_id': distribution.lieu.commune_id,
            'commune_total_quantite': commune_stats['total'],
            'commune_quantite_distribuee': commune_stats['distribuee'],
        })

    except Http404:
        raise
    except Exception as e:
        logger.exception(
            "Erreur update_distribution_quantite campagne=%s distribution=%s",
            campagne_pk, pk,
        )
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def bulk_set_quantites(request, pk):
    """Appliquer une quantité identique à plusieurs lieux d'une campagne (AJAX).

    Corps JSON attendu : {"quantite": <entier >= 0>, "scope": "all"|"only_zero"}.
    - "all" : écrase toutes les quantités de la campagne.
    - "only_zero" : ne remplit que les lignes encore à 0.
    1 UPDATE en transaction + 1 aggregate + 1 requête par-commune.
    """
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        campagne = get_object_or_404(CampagneDistribution, pk=pk)

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

        quantite, erreur = _parse_quantite(payload.get('quantite'))
        if erreur:
            return JsonResponse({'error': erreur}, status=400)

        scope = payload.get('scope', 'all')
        if scope not in ('all', 'only_zero'):
            return JsonResponse({'error': 'Scope invalide'}, status=400)

        scoped = Distribution.objects.filter(campagne=campagne)
        if scope == 'only_zero':
            scoped = scoped.filter(quantite=0)

        if scoped.count() > 1000:
            return JsonResponse(
                {'error': 'Trop de distributions (max 1000)'}, status=400
            )

        with transaction.atomic():
            updated_count = scoped.update(quantite=quantite)
            totaux = _campagne_quantite_totals(campagne)
            communes_quantites = _all_communes_quantites(campagne)

        return JsonResponse({
            'success': True,
            'updated_count': updated_count,
            'quantite': quantite,
            'scope': scope,
            'total_quantite': totaux['total_quantite'],
            'quantite_distribuee': totaux['quantite_distribuee'],
            'communes_quantites': communes_quantites,
        })

    except Http404:
        raise
    except Exception as e:
        logger.exception("Erreur bulk_set_quantites campagne=%s", pk)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def retirer_lieu_campagne(request, pk, dist_pk):
    """Retirer un lieu d'une campagne (AJAX).

    Supprime physiquement la ligne Distribution (scoped à la campagne)
    et mémorise le retrait dans CampagneLieuExclusion pour que la
    synchronisation ne recrée pas le lieu. Le lieu lui-même est conservé.
    Idempotent : un retrait déjà effectué renvoie success/removed=False.
    """
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        campagne = get_object_or_404(CampagneDistribution, pk=pk)
        distribution = Distribution.objects.filter(
            pk=dist_pk
        ).select_related('lieu__commune').first()
        if distribution is None:
            # Ligne inexistante (déjà retirée ou jamais créée) : idempotent.
            totaux = _campagne_quantite_totals(campagne)
            return JsonResponse({
                'success': True,
                'removed': False,
                'total_quantite': totaux['total_quantite'],
                'quantite_distribuee': totaux['quantite_distribuee'],
            })
        if distribution.campagne_id != campagne.pk:
            return JsonResponse(
                {'error': 'Distribution hors campagne'}, status=404
            )

        lieu = distribution.lieu
        commune_id = lieu.commune_id
        with transaction.atomic():
            CampagneLieuExclusion.objects.get_or_create(
                campagne=campagne, lieu=lieu,
                defaults={'excluded_by': request.user},
            )
            distribution.delete()
            totaux = _campagne_quantite_totals(campagne)
            commune_stats = _commune_quantite_totals(campagne, commune_id)

        return JsonResponse({
            'success': True,
            'removed': True,
            'distribution_id': dist_pk,
            'lieu_id': lieu.pk,
            'commune_id': commune_id,
            'total_quantite': totaux['total_quantite'],
            'quantite_distribuee': totaux['quantite_distribuee'],
            'commune_total_quantite': commune_stats['total'],
            'commune_quantite_distribuee': commune_stats['distribuee'],
        })

    except Http404:
        raise
    except Exception as e:
        logger.exception(
            "Erreur retirer_lieu_campagne campagne=%s distribution=%s",
            pk, dist_pk,
        )
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def reintegrer_lieu_campagne(request, pk, lieu_pk):
    """Réintégrer un lieu retiré dans une campagne (AJAX).

    Supprime la trace d'exclusion et recrée la ligne Distribution
    (quantité 0, non distribuée). 404 si aucune exclusion n'existe.
    """
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    try:
        campagne = get_object_or_404(CampagneDistribution, pk=pk)
        lieu = get_object_or_404(Lieu, pk=lieu_pk)
        exclusion = CampagneLieuExclusion.objects.filter(
            campagne=campagne, lieu=lieu
        ).first()
        if exclusion is None:
            return JsonResponse(
                {'error': 'Ce lieu n\'est pas retiré de cette campagne'},
                status=404,
            )

        with transaction.atomic():
            exclusion.delete()
            distribution, _ = Distribution.objects.get_or_create(
                campagne=campagne, lieu=lieu,
                defaults={'is_distributed': False, 'quantite': 0},
            )
            totaux = _campagne_quantite_totals(campagne)
            commune_stats = _commune_quantite_totals(
                campagne, lieu.commune_id
            )

        return JsonResponse({
            'success': True,
            'distribution_id': distribution.pk,
            'commune_id': lieu.commune_id,
            'total_quantite': totaux['total_quantite'],
            'quantite_distribuee': totaux['quantite_distribuee'],
            'commune_total_quantite': commune_stats['total'],
            'commune_quantite_distribuee': commune_stats['distribuee'],
        })

    except Http404:
        raise
    except Exception as e:
        logger.exception(
            "Erreur reintegrer_lieu_campagne campagne=%s lieu=%s",
            pk, lieu_pk,
        )
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def sync_campagne_lieux(request, pk):
    """Synchroniser les lieux d'une campagne avec tous les lieux actifs"""
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    
    try:
        campagne = get_object_or_404(CampagneDistribution, pk=pk)
        
        # Récupérer tous les lieux actifs
        lieux_actifs = Lieu.objects.filter(is_active=True)
        
        # Récupérer les IDs des lieux déjà liés à cette campagne (1 requête)
        existing_lieu_ids = set(
            campagne.distributions.values_list('lieu_id', flat=True)
        )

        # Lieux retirés de cette campagne : jamais recréés par la synchro.
        excluded_lieu_ids = set(
            campagne.lieux_exclus.values_list('lieu_id', flat=True)
        )

        # Créer les distributions manquantes en une seule requête
        distributions_to_create = [
            Distribution(
                campagne=campagne, lieu=lieu,
                is_distributed=False, quantite=0,
            )
            for lieu in lieux_actifs
            if lieu.id not in existing_lieu_ids
            and lieu.id not in excluded_lieu_ids
        ]

        skipped_count = len([
            lieu for lieu in lieux_actifs
            if lieu.id not in existing_lieu_ids
            and lieu.id in excluded_lieu_ids
        ])

        created_count = 0
        if distributions_to_create:
            with transaction.atomic():
                created_count = len(Distribution.objects.bulk_create(distributions_to_create))

        message = (
            f'{created_count} nouveau(x) lieu(x) ajouté(s) à la campagne'
        )
        if skipped_count:
            message += (
                f', {skipped_count} ignoré(s) car retiré(s) de la campagne'
            )

        return JsonResponse({
            'success': True,
            'message': message,
            'created_count': created_count,
            'skipped_count': skipped_count,
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def commune_list(request):
    """Liste des communes"""
    if not is_distribution_manager(request.user):
        return redirect('distribution:access_denied')
    
    communes = Commune.objects.annotate(
        lieux_count=Count('lieux', filter=Q(lieux__is_active=True))
    ).order_by('name')
    
    context = {'communes': communes}
    return render(request, 'distribution/commune_list.html', context)


@login_required
def commune_detail(request, pk):
    """Détail d'une commune avec ses lieux"""
    if not is_distribution_manager(request.user):
        return redirect('distribution:access_denied')
    
    commune = get_object_or_404(Commune, pk=pk)
    lieux = commune.lieux.all().order_by('name')
    
    context = {
        'commune': commune,
        'lieux': lieux,
    }
    return render(request, 'distribution/commune_detail.html', context)


@login_required
def commune_create(request):
    """Créer une nouvelle commune"""
    if not is_distribution_manager(request.user):
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

    if not is_distribution_manager(request.user):
        logger.warning("Access denied for user %s on commune %s", request.user, commune_pk)
        return redirect('distribution:access_denied')

    commune = get_object_or_404(Commune, pk=commune_pk)

    if request.method == 'POST':
        logger.debug("POST data received for commune %s", commune_pk)
        form = LieuForm(request.POST, instance=Lieu(commune=commune))
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
def lieu_edit_modal(request, commune_pk, pk):
    """Vue HTMX : retourne le fragment HTML de la modale d'édition d'un lieu"""
    if not is_distribution_manager(request.user):
        if request.headers.get('HX-Request'):
            return JsonResponse({'error': 'Accès refusé'}, status=403)
        return redirect('distribution:access_denied')

    lieu = get_object_or_404(Lieu, pk=pk, commune_id=commune_pk)
    form = LieuForm(instance=lieu)

    html = render_to_string(
        'distribution/partials/lieu_modal.html',
        {'form': form, 'lieu': lieu, 'commune': lieu.commune},
        request=request,
    )
    return HttpResponse(html)


@login_required
@require_POST
def lieu_update(request, commune_pk, pk):
    """Vue HTMX : met à jour un lieu depuis la modale d'édition"""
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    lieu = get_object_or_404(Lieu, pk=pk, commune_id=commune_pk)
    form = LieuForm(request.POST, instance=lieu)
    if form.is_valid():
        lieu = form.save()
        logger.info(
            "Lieu updated: %s in %s by %s",
            lieu.name, lieu.commune.name, request.user,
        )
        card_html = render_to_string(
            'distribution/partials/lieu_card.html',
            {'lieu': lieu, 'commune': lieu.commune},
            request=request,
        )
        return JsonResponse({
            'success': True,
            'lieu_id': lieu.pk,
            'card_html': card_html,
        })

    errors = {}
    for field, field_errors in form.errors.items():
        errors[field] = [str(e) for e in field_errors]
    return JsonResponse(
        {'error': 'Formulaire invalide', 'errors': errors}, status=400
    )


@login_required
@require_POST
def lieu_toggle(request, commune_pk, pk):
    """Vue HTMX : active/désactive un lieu"""
    if not is_distribution_manager(request.user):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    lieu = get_object_or_404(Lieu, pk=pk, commune_id=commune_pk)
    lieu.is_active = not lieu.is_active
    lieu.save()
    logger.info(
        "Lieu %s is_active=%s by %s",
        lieu.name, lieu.is_active, request.user,
    )
    return render(
        request,
        'distribution/partials/lieu_card.html',
        {'lieu': lieu, 'commune': lieu.commune},
    )


@login_required
def lieu_delete(request, commune_pk, pk):
    """Supprimer définitivement un lieu (confirmation en GET, suppression en POST).

    La suppression efface le lieu et ses lignes Distribution / exclusions
    (CASCADE) : il disparaît des lieux globaux et de toutes les campagnes.
    La commune et les autres lieux sont conservés.
    """
    if not is_distribution_manager(request.user):
        return redirect('distribution:access_denied')

    commune = get_object_or_404(Commune, pk=commune_pk)
    lieu = get_object_or_404(Lieu, pk=pk, commune=commune)

    stats = Distribution.objects.filter(lieu=lieu).aggregate(
        total=Count('id'),
        distribuees=Count('id', filter=Q(is_distributed=True)),
        quantite=Coalesce(Sum('quantite'), 0),
    )
    campagnes = list(
        CampagneDistribution.objects.filter(
            distributions__lieu=lieu
        ).distinct().values_list('name', flat=True)
    )

    if request.method == 'POST':
        name = lieu.name
        campagnes_count = len(campagnes)
        lieu.delete()
        logger.info(
            "Lieu deleted: %s in %s by %s", name, commune.name, request.user
        )
        messages.success(
            request,
            f'Lieu "{name}" supprimé définitivement '
            f'({campagnes_count} campagne(s) concernée(s)). '
            'La commune et les autres lieux sont conservés.'
        )
        return redirect('distribution:commune_detail', pk=commune.pk)

    context = {
        'commune': commune,
        'lieu': lieu,
        'stats': stats,
        'campagnes': campagnes,
    }
    return render(request, 'distribution/lieu_confirm_delete.html', context)


@login_required
def statistics(request):
    """Page des statistiques"""
    if not is_distribution_manager(request.user):
        return redirect('distribution:access_denied')
    
    # Statistiques générales
    total_campagnes = CampagneDistribution.objects.count()
    today = timezone.localdate()
    campagnes_actives = CampagneDistribution.objects.filter(
        status='active', end_date__gte=today
    ).count()
    campagnes_terminees = CampagneDistribution.objects.filter(
        Q(status='completed') | Q(status='active', end_date__lt=today)
    ).count()
    campagnes_drafts = CampagneDistribution.objects.filter(
        status='draft'
    ).count()
    campagnes_cancelled = CampagneDistribution.objects.filter(
        status='cancelled'
    ).count()

    distributions_stats = Distribution.objects.aggregate(
        total=Count('id'),
        distribuees=Count('id', filter=Q(is_distributed=True)),
        flyers_prevus=Coalesce(Sum('quantite'), 0),
        flyers_distribues=Coalesce(
            Sum('quantite', filter=Q(is_distributed=True)), 0
        ),
    )
    distributions_total = distributions_stats['total']
    distributions_distribuees = distributions_stats['distribuees']
    flyers_prevus = distributions_stats['flyers_prevus']
    flyers_distribues = distributions_stats['flyers_distribues']

    total_communes = Commune.objects.count()
    total_lieux = Lieu.objects.filter(is_active=True).count()

    # Top des communes par nombre de lieux
    top_communes = Commune.objects.annotate(
        lieux_count=Count('lieux', filter=Q(lieux__is_active=True))
    ).order_by('-lieux_count')[:5]

    # Campagnes récentes (même tri que la liste : fin la plus proche
    # en premier, campagnes expirées en bas)
    campagnes_recentes = CampagneDistribution.objects.select_related(
        'created_by'
    ).annotate(
        _total_lieux=Count('distributions'),
        _lieux_distribues=Count('distributions', filter=Q(distributions__is_distributed=True)),
        **_quantite_annotations()
    ).order_by(
        Case(
            When(end_date__lt=today, then=Value(1)),
            default=Value(0),
        ),
        'end_date',
    )[:5]

    context = {
        'total_campagnes': total_campagnes,
        'campagnes_actives': campagnes_actives,
        'campagnes_terminees': campagnes_terminees,
        'campagnes_drafts': campagnes_drafts,
        'campagnes_cancelled': campagnes_cancelled,
        'distributions_total': distributions_total,
        'distributions_distribuees': distributions_distribuees,
        'flyers_prevus': flyers_prevus,
        'flyers_distribues': flyers_distribues,
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