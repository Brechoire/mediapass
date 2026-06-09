from django.urls import path
from . import views

app_name = "library_workshops"

urlpatterns = [
    path("", views.index, name="index"),
    path("create/", views.create_workshop, name="create_workshop"),
    path("edit/<int:workshop_id>/", views.edit_workshop, name="edit_workshop"),
    path("delete/<int:workshop_id>/", views.delete_workshop, name="delete_workshop"),
    path("access-denied/", views.access_denied, name="access_denied"),
    # Gestion des participants
    path("archives/", views.workshop_archives, name="archives"),
    path("statistics/", views.workshop_statistics, name="statistics"),
    path(
        "workshop/<int:workshop_id>/detail/",
        views.workshop_detail,
        name="workshop_detail",
    ),
    path(
        "workshop/<int:workshop_id>/participants/",
        views.workshop_participants,
        name="workshop_participants",
    ),
    path(
        "workshop/<int:workshop_id>/add-participant/",
        views.add_participant,
        name="add_participant",
    ),
    path(
        "workshop/<int:workshop_id>/add-group-reservation/",
        views.add_group_reservation,
        name="add_group_reservation",
    ),
    path(
        "workshop/<int:workshop_id>/remove-participant/<int:participant_id>/",
        views.remove_participant,
        name="remove_participant",
    ),
    path(
        "workshop/<int:workshop_id>/remove-group/<int:participant_id>/",
        views.remove_group,
        name="remove_group",
    ),
    path(
        "workshop/<int:workshop_id>/move-to-waiting/<int:participant_id>/",
        views.move_to_waiting_list,
        name="move_to_waiting_list",
    ),
    path(
        "workshop/<int:workshop_id>/move-from-waiting/<int:participant_id>/",
        views.move_from_waiting_list,
        name="move_from_waiting_list",
    ),
    # Recherche titres (HTMX autocomplete)
    path("search-titles/", views.search_workshop_titles, name="search_titles"),
    # Gestion des lieux (HTMX)
    path(
        "location/create/modal/",
        views.create_location_modal,
        name="create_location_modal",
    ),
    path("location/create/", views.create_location, name="create_location"),
    # Calendrier
    path("calendar/", views.workshop_calendar, name="workshop_calendar"),
    path(
        "calendar/events/",
        views.workshop_calendar_events,
        name="workshop_calendar_events",
    ),
    # Duplication
    path(
        "workshop/<int:workshop_id>/duplicate/",
        views.duplicate_workshop,
        name="duplicate_workshop",
    ),
    # Newsletter
    path("newsletter/", views.newsletter_view, name="newsletter"),
    # Récurrence
    path("recurrence/preview/", views.recurrence_preview, name="recurrence_preview"),
    path("recurrence/holidays/", views.recurrence_holidays, name="recurrence_holidays"),
]
