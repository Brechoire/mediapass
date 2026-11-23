from django.contrib import admin
from .models import Closure, Location, VisitorCount


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'icon', 'color', 'is_active', 'order', 'created_at')
    list_filter = ('is_active', 'user')
    list_editable = ('order', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('order', 'name')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'user')
        }),
        ('Affichage', {
            'fields': ('icon', 'color', 'order', 'is_active')
        }),
    )


@admin.register(VisitorCount)
class VisitorCountAdmin(admin.ModelAdmin):
    list_display = ('location', 'date', 'count', 'created_by', 'updated_by', 'updated_at')
    list_filter = ('location', 'date', 'created_by')
    search_fields = ('location__name',)
    date_hierarchy = 'date'
    ordering = ('-date', 'location__order')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        (None, {
            'fields': ('location', 'date', 'count')
        }),
        ('Informations', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Closure)
class ClosureAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "start_date",
        "end_date",
        "kind",
        "label",
        "created_by",
    )
    list_filter = ("kind", "user", "start_date")
    search_fields = ("user__username", "label")
    date_hierarchy = "start_date"
    ordering = ("-start_date", "-end_date")
    readonly_fields = ("created_at", "updated_at")

