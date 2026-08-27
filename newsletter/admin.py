from django.contrib import admin

from .models import Block, LibraryProfile, Newsletter, NewsletterImage, Section


@admin.register(LibraryProfile)
class LibraryProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "phone", "updated_at")
    search_fields = ("name", "user__username", "user__last_name")


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("position", "title", "library_profile", "background_color")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "newsletter", "position", "library_profile")
    list_filter = ("newsletter",)
    raw_id_fields = ("newsletter", "library_profile")


class BlockInline(admin.TabularInline):
    model = Block
    extra = 0
    fields = ("position", "block_type", "content", "style")


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "period_start",
        "period_end",
        "status",
        "sender_campaign_id",
        "created_by",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("title", "subject")
    inlines = [SectionInline, BlockInline]


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("__str__", "newsletter", "section", "position", "block_type")
    list_filter = ("block_type",)
    raw_id_fields = ("newsletter", "section")


@admin.register(NewsletterImage)
class NewsletterImageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "uploaded_by", "created_at")
