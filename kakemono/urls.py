"""URLs configuration for analytics app."""

from django.urls import path

from . import views

app_name = "kakemono"

urlpatterns = [
    path("", views.kakemono_list, name="list"),
    path("create/", views.kakemono_create, name="create"),
    path("<int:pk>/", views.kakemono_detail, name="detail"),
    path("<int:pk>/update/", views.kakemono_update, name="update"),
    path("<int:pk>/delete/", views.kakemono_delete, name="delete"),
    path(
        "reservation/create/",
        views.reservation_create,
        name="reservation-create",
    ),
    path(
        "reservation/<int:pk>/",
        views.reservation_detail,
        name="reservation-detail",
    ),
    path(
        "reservation/<int:pk>/update/",
        views.reservation_update,
        name="reservation-update",
    ),
    path(
        "reservation/<int:pk>/delete/",
        views.reservation_delete,
        name="reservation-delete",
    ),
    path("reservations/", views.reservation_list, name="reservation-list"),
    path(
        "api/check-availability/",
        views.check_availability,
        name="check_availability",
    ),
    path("api/reservations/", views.get_reservations, name="get-reservations"),
]
