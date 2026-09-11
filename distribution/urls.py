from django.urls import path
from . import views

app_name = 'distribution'

urlpatterns = [
    # Pages principales
    path('', views.index, name='index'),
    path('statistics/', views.statistics, name='statistics'),
    path('access-denied/', views.access_denied, name='access_denied'),
    
    # Gestion des campagnes
    path('campagnes/', views.campagne_list, name='campagne_list'),
    path('campagnes/create/', views.campagne_create, name='campagne_create'),
    path('campagnes/<int:pk>/', views.campagne_detail, name='campagne_detail'),
    path('campagnes/<int:pk>/edit/', views.campagne_edit,
         name='campagne_edit'),
    path('campagnes/<int:pk>/delete/', views.campagne_delete,
         name='campagne_delete'),

    # Gestion des distributions (AJAX)
    path('distributions/<int:pk>/toggle/', views.toggle_distribution,
         name='toggle_distribution'),
    path('distributions/<int:pk>/force-validate/', views.force_validate_distribution,
         name='force_validate_distribution'),
    path('campagnes/<int:pk>/bulk-update/', views.bulk_update_distributions,
         name='bulk_update_distributions'),
    path('campagnes/<int:pk>/bulk-set-quantites/', views.bulk_set_quantites,
         name='bulk_set_quantites'),
    path('campagnes/<int:campagne_pk>/distributions/<int:pk>/quantite/',
         views.update_distribution_quantite,
         name='update_distribution_quantite'),
    path('campagnes/<int:pk>/sync-lieux/', views.sync_campagne_lieux,
         name='sync_campagne_lieux'),
    path('campagnes/<int:pk>/distributions/<int:dist_pk>/retirer/',
         views.retirer_lieu_campagne,
         name='retirer_lieu_campagne'),
    path('campagnes/<int:pk>/lieux/<int:lieu_pk>/reintegrer/',
         views.reintegrer_lieu_campagne,
         name='reintegrer_lieu_campagne'),
    
    # Gestion des communes
    path('communes/', views.commune_list, name='commune_list'),
    path('communes/create/', views.commune_create, name='commune_create'),
    path('communes/<int:pk>/', views.commune_detail, name='commune_detail'),
    path('communes/<int:commune_pk>/lieux/create/', views.lieu_create, name='lieu_create'),
    path('communes/<int:commune_pk>/lieux/<int:pk>/edit/', views.lieu_edit_modal,
         name='lieu_edit_modal'),
    path('communes/<int:commune_pk>/lieux/<int:pk>/update/', views.lieu_update,
         name='lieu_update'),
    path('communes/<int:commune_pk>/lieux/<int:pk>/toggle/', views.lieu_toggle,
         name='lieu_toggle'),
]
