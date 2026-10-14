"""Admin configuration for the documents app."""

from django.contrib import admin

from .models import Document, DocumentCategory


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    """Administration des catégories de documents."""

    list_display = ("name", "icon", "display_order", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("display_order", "name")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Administration des documents PDF."""

    list_display = (
        "title",
        "category",
        "is_published",
        "display_order",
        "updated_at",
    )
    list_filter = ("is_published", "category")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("category",)
    ordering = ("display_order", "title")
