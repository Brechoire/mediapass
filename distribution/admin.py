from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import Commune, Lieu, CampagneDistribution, Distribution


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ['name', 'lieux_count', 'lieux_actifs_count', 'created_at']
    list_filter = ['created_at', 'lieux__is_active']
    search_fields = ['name']
    ordering = ['name']
    list_per_page = 25

    def lieux_count(self, obj):
        return obj.lieux.count()
    lieux_count.short_description = 'Total lieux'

    def lieux_actifs_count(self, obj):
        return obj.lieux.filter(is_active=True).count()
    lieux_actifs_count.short_description = 'Lieux actifs'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_lieux=Count('lieux'),
            lieux_actifs=Count('lieux', filter=Q(lieux__is_active=True))
        )


@admin.register(Lieu)
class LieuAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'commune', 'is_active', 'distributions_count', 'created_at'
    ]
    list_filter = ['is_active', 'commune', 'created_at']
    search_fields = ['name', 'commune__name', 'description']
    ordering = ['commune__name', 'name']
    list_per_page = 25
    actions = ['activate_lieux', 'deactivate_lieux']

    def distributions_count(self, obj):
        return obj.distributions.count()
    distributions_count.short_description = 'Distributions'

    def activate_lieux(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request, f'{updated} lieu(x) activé(s) avec succès.'
        )
    activate_lieux.short_description = "Activer les lieux sélectionnés"

    def deactivate_lieux(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request, f'{updated} lieu(x) désactivé(s) avec succès.'
        )
    deactivate_lieux.short_description = "Désactiver les lieux sélectionnés"


class DistributionInline(admin.TabularInline):
    model = Distribution
    extra = 0
    fields = [
        'lieu', 'is_distributed', 'distributed_by', 'distributed_at', 'notes'
    ]
    readonly_fields = ['distributed_at']
    can_delete = False
    ordering = ['lieu__commune__name', 'lieu__name']


@admin.register(CampagneDistribution)
class CampagneDistributionAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status', 'start_date', 'end_date',
        'progression_display', 'is_completed_display', 'created_by',
        'created_at'
    ]
    list_filter = [
        'status', 'created_at', 'start_date', 'end_date', 'created_by'
    ]
    search_fields = ['name', 'description', 'created_by__username']
    ordering = ['-created_at']
    inlines = [DistributionInline]
    list_per_page = 25
    actions = ['mark_as_active', 'mark_as_completed', 'mark_as_cancelled']

    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'description', 'status')
        }),
        ('Période', {
            'fields': ('start_date', 'end_date')
        }),
        ('Métadonnées', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    def progression_display(self, obj):
        if obj.total_lieux == 0:
            return "Aucun lieu"
        return f"{obj.lieux_distribues}/{obj.total_lieux} ({obj.progression}%)"
    progression_display.short_description = 'Progression'

    def is_completed_display(self, obj):
        if obj.is_completed:
            return format_html(
                '<span style="color: green; font-weight: bold;">'
                '✓ Complet</span>'
            )
        elif obj.status == 'cancelled':
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Annulé</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">'
                'En cours</span>'
            )
    is_completed_display.short_description = 'Statut'

    def mark_as_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(
            request, f'{updated} campagne(s) marquée(s) comme active(s).'
        )
    mark_as_active.short_description = "Marquer comme actives"

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(
            request, f'{updated} campagne(s) marquée(s) comme terminée(s).'
        )
    mark_as_completed.short_description = "Marquer comme terminées"

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(
            request, f'{updated} campagne(s) marquée(s) comme annulée(s).'
        )
    mark_as_cancelled.short_description = "Marquer comme annulées"

    def save_model(self, request, obj, form, change):
        if not change:  # Nouvelle campagne
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    list_display = [
        'campagne', 'lieu', 'is_distributed_display',
        'distributed_by', 'distributed_at', 'created_at'
    ]
    list_filter = [
        'is_distributed', 'distributed_at', 'created_at',
        'campagne__status', 'lieu__commune'
    ]
    search_fields = [
        'campagne__name', 'lieu__name', 'lieu__commune__name',
        'distributed_by__username', 'notes'
    ]
    ordering = ['-created_at']
    list_per_page = 50
    actions = ['mark_as_distributed', 'mark_as_not_distributed']

    fieldsets = (
        ('Distribution', {
            'fields': ('campagne', 'lieu', 'is_distributed')
        }),
        ('Détails', {
            'fields': ('distributed_by', 'distributed_at', 'notes')
        }),
    )

    readonly_fields = ['distributed_at']

    def is_distributed_display(self, obj):
        if obj.is_distributed:
            return format_html(
                '<span style="color: green; font-weight: bold;">'
                '✓ Distribué</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">'
                '✗ Non distribué</span>'
            )
    is_distributed_display.short_description = 'Distribué'

    def mark_as_distributed(self, request, queryset):
        updated = queryset.update(
            is_distributed=True, distributed_by=request.user
        )
        self.message_user(
            request, f'{updated} distribution(s) marquée(s) comme '
            f'distribuée(s).'
        )
    mark_as_distributed.short_description = "Marquer comme distribuées"

    def mark_as_not_distributed(self, request, queryset):
        updated = queryset.update(
            is_distributed=False, distributed_by=None
        )
        self.message_user(
            request, f'{updated} distribution(s) marquée(s) comme '
            f'non distribuée(s).'
        )
    mark_as_not_distributed.short_description = "Marquer comme non distribuées"

    def save_model(self, request, obj, form, change):
        if obj.is_distributed and not obj.distributed_by:
            obj.distributed_by = request.user
        super().save_model(request, obj, form, change)


# Configuration de l'interface d'administration
admin.site.site_header = "Administration MediaPass - Distribution"
admin.site.site_title = "MediaPass Distribution"
admin.site.index_title = "Gestion des distributions de flyers"

# Personnalisation des messages
admin.site.empty_value_display = "Non renseigné"