from django.urls import path
from . import views

app_name = "visitor_tracking"

urlpatterns = [
    # Dashboard principal
    path("", views.index, name="index"),
    
    # Actions temps réel
    path("increment/<int:location_id>/", views.increment_count, name="increment"),
    path("increment/<int:location_id>/<int:amount>/", views.increment_count, name="increment_amount"),
    path("decrement/<int:location_id>/", views.decrement_count, name="decrement"),
    
    # Gestion des espaces
    path("spaces/add/", views.add_space, name="add_space"),
    path("spaces/edit/<int:location_id>/", views.edit_space, name="edit_space"),
    path("spaces/delete/<int:location_id>/", views.delete_space, name="delete_space"),
    
    # Saisie rétroactive
    path("entry/", views.entry_form, name="entry_form"),
    
    # Statistiques
    path("statistics/", views.statistics, name="statistics"),
    path("admin-statistics/", views.superadmin_statistics, name="superadmin_statistics"),
    path("export/csv/", views.export_csv, name="export_csv"),
    
    # Historique et modification
    path("history/", views.history, name="history"),
    path("edit/<int:entry_id>/", views.edit_entry, name="edit_entry"),
    path("delete/<int:entry_id>/", views.delete_entry, name="delete_entry"),
]

