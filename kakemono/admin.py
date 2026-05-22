"""Admin configuration for Kakemono models."""
from django.contrib import admin
from .models import Kakemono, KakemonoReservation


@admin.register(Kakemono)
class KakemonoAdmin(admin.ModelAdmin):
    """Administration des œuvres Kakemono."""
    list_display = ("title", "is_available", "created_at", "updated_at")
    list_filter = ("is_available", "created_at")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("title",)


@admin.register(KakemonoReservation)
class KakemonoReservationAdmin(admin.ModelAdmin):
    """Administration des réservations d'œuvres Kakemono."""
    list_display = (
        "id",
        "last_name",
        "first_name",
        "start_date",
        "end_date",
        "status",
        "created_at",
    )
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("user__username", "user__email", "notes")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)
    filter_horizontal = ("kakemonos",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")
