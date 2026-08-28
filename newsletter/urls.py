from django.urls import path

from . import views

app_name = "newsletter"

urlpatterns = [
    path("", views.index, name="index"),
    path("fiches/", views.fiche_list, name="fiche_list"),
    path("fiches/<int:profile_id>/edit/", views.fiche_edit, name="fiche_edit"),
    path("ma-fiche/", views.ma_fiche, name="ma_fiche"),
    path("<int:pk>/", views.builder, name="builder"),
    path("<int:pk>/candidats/", views.candidates_tab, name="candidates"),
    path(
        "<int:pk>/candidats/panneau/",
        views.candidates_panel,
        name="candidates_panel",
    ),
    path(
        "<int:pk>/candidats/refresh/",
        views.candidates_refresh,
        name="candidates_refresh",
    ),
    path("<int:pk>/parametres/", views.settings_update, name="settings_update"),
    path(
        "<int:pk>/parametres/panneau/",
        views.settings_panel,
        name="settings_panel",
    ),
    path("<int:pk>/blocs/add/", views.add_block, name="add_block"),
    path("<int:pk>/blocs/bulk/", views.bulk_add_workshops, name="bulk_add_workshops"),
    path("<int:pk>/sections/add/", views.add_section, name="add_section"),
    path(
        "<int:pk>/sections/<int:section_id>/edit/",
        views.edit_section_panel,
        name="edit_section",
    ),
    path(
        "<int:pk>/sections/<int:section_id>/update/",
        views.update_section,
        name="update_section",
    ),
    path(
        "<int:pk>/sections/<int:section_id>/move/<str:direction>/",
        views.move_section,
        name="move_section",
    ),
    path(
        "<int:pk>/sections/<int:section_id>/delete/",
        views.delete_section,
        name="delete_section",
    ),
    path("<int:pk>/sections/reorder/", views.reorder_sections, name="reorder_sections"),
    path("<int:pk>/blocks/reorder/", views.reorder_blocks, name="reorder_blocks"),
    path("<int:pk>/clear/", views.clear_layout, name="clear_layout"),
    path(
        "<int:pk>/blocs/<int:block_id>/edit/",
        views.edit_panel,
        name="edit_block",
    ),
    path(
        "<int:pk>/blocs/<int:block_id>/update/",
        views.update_block,
        name="update_block",
    ),
    path(
        "<int:pk>/blocs/<int:block_id>/move/<str:direction>/",
        views.move_block,
        name="move_block",
    ),
    path(
        "<int:pk>/blocs/<int:block_id>/duplicate/",
        views.duplicate_block,
        name="duplicate_block",
    ),
    path(
        "<int:pk>/blocs/<int:block_id>/delete/",
        views.delete_block,
        name="delete_block",
    ),
    path("<int:pk>/apercu/", views.preview, name="preview"),
    path("<int:pk>/telecharger/", views.download, name="download"),
    path("<int:pk>/contacts.csv/", views.contacts_csv, name="contacts_csv"),
    path("<int:pk>/sender/", views.send_sender, name="send_sender"),
    path("<int:pk>/dupliquer/", views.duplicate_newsletter, name="duplicate"),
    path("<int:pk>/supprimer/", views.delete_newsletter, name="delete"),
    path("presets/", views.preset_list, name="preset_list"),
    path("presets/nouveau/", views.preset_create, name="preset_create"),
    path(
        "presets/<int:pk>/editer/",
        views.preset_edit,
        name="preset_edit",
    ),
    path(
        "presets/<int:pk>/supprimer/",
        views.preset_delete,
        name="preset_delete",
    ),
    path(
        "<int:pk>/sections/<int:section_id>/preset/<int:preset_id>/",
        views.apply_preset,
        name="apply_preset",
    ),
]
