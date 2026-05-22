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

    # Gestion des distributions (AJAX)
    path('distributions/<int:pk>/toggle/', views.toggle_distribution,
         name='toggle_distribution'),
    path('distributions/<int:pk>/force-validate/', views.force_validate_distribution,
         name='force_validate_distribution'),
    path('campagnes/<int:pk>/sync-lieux/', views.sync_campagne_lieux,
         name='sync_campagne_lieux'),
    
    # Gestion des communes
    path('communes/', views.commune_list, name='commune_list'),
    path('communes/create/', views.commune_create, name='commune_create'),
    path('communes/<int:pk>/', views.commune_detail, name='commune_detail'),
    path('communes/<int:commune_pk>/lieux/create/', views.lieu_create, name='lieu_create'),
]
