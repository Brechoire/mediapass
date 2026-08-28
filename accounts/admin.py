from django.contrib import admin

from .models import LibraryProfile


@admin.register(LibraryProfile)
class LibraryProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "phone", "updated_at")
    search_fields = ("name", "user__username", "user__last_name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")
