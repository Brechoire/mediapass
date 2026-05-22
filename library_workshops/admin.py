from django.contrib import admin
from django.utils.html import format_html
from .models import Workshop, WorkshopParticipant, WorkshopCategory


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = [
        'title', 
        'age_range_display', 
        'start_date', 
        'start_time', 
        'location', 
        'participants_count', 
        'capacity_status',
        'newsletter_status',
        'created_by'
    ]
    list_filter = [
        'start_date', 
        'is_all_ages', 
        'newsletter', 
        'is_class_welcome', 
        'created_at'
    ]
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['created_at', 'updated_at', 'participants_count']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('title', 'description', 'location')
        }),
        ('Dates et horaires', {
            'fields': ('start_date', 'end_date', 'start_time', 'end_time')
        }),
        ('Public cible', {
            'fields': ('is_all_ages', 'min_age', 'max_age'),
            'description': 'Définissez la tranche d\'âge cible pour cet atelier'
        }),
        ('Capacité et organisation', {
            'fields': ('max_participants', 'is_class_welcome')
        }),
        ('Communication', {
            'fields': ('newsletter',)
        }),
        ('Visuel', {
            'fields': ('poster',)
        }),
        ('Métadonnées', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def participants_count(self, obj):
        """Affiche le nombre de participants avec un badge coloré"""
        count = obj.current_participants_count
        max_count = obj.max_participants
        
        if count >= max_count:
            color = 'danger'
            text = f'{count}/{max_count} - Complet'
        elif count >= max_count * 0.8:
            color = 'warning'
            text = f'{count}/{max_count} - Presque complet'
        else:
            color = 'success'
            text = f'{count}/{max_count}'
            
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, text
        )
    participants_count.short_description = 'Participants'
    
    def capacity_status(self, obj):
        """Affiche le statut de capacité"""
        if obj.is_full:
            return format_html('<span class="badge bg-danger">Complet</span>')
        elif obj.available_spots <= 3:
            return format_html('<span class="badge bg-warning">{} places</span>', obj.available_spots)
        else:
            return format_html('<span class="badge bg-success">{} places</span>', obj.available_spots)
    capacity_status.short_description = 'Disponibilité'
    
    def newsletter_status(self, obj):
        """Affiche le statut de la newsletter"""
        if obj.newsletter:
            return format_html('<span class="badge bg-success">Oui</span>')
        else:
            return format_html('<span class="badge bg-secondary">Non</span>')
    newsletter_status.short_description = 'Newsletter'
    
    def save_model(self, request, obj, form, change):
        """Sauvegarde automatique du créateur"""
        if not change:  # Nouvel objet
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WorkshopParticipant)
class WorkshopParticipantAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 
        'workshop', 
        'age_display', 
        'status', 
        'registration_date',
        'contact_info'
    ]
    list_filter = [
        'status', 
        'registration_date', 
        'workshop__start_date',
        'added_by'
    ]
    search_fields = ['first_name', 'last_name', 'email', 'workshop__title']
    readonly_fields = ['registration_date']
    date_hierarchy = 'registration_date'
    
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('first_name', 'last_name', 'age')
        }),
        ('Contact', {
            'fields': ('email', 'phone')
        }),
        ('Inscription', {
            'fields': ('workshop', 'status', 'registration_date')
        }),
        ('Gestion', {
            'fields': ('notes', 'added_by'),
            'classes': ('collapse',)
        }),
    )
    
    def contact_info(self, obj):
        """Affiche les informations de contact"""
        contact = []
        if obj.email:
            contact.append(f'📧 {obj.email}')
        if obj.phone:
            contact.append(f'📞 {obj.phone}')
        
        if contact:
            return format_html('<br>'.join(contact))
        return 'Aucun contact'
    contact_info.short_description = 'Contact'
    
    def save_model(self, request, obj, form, change):
        """Sauvegarde automatique de l'ajouteur"""
        if not change:  # Nouvel objet
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WorkshopCategory)
class WorkshopCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display', 'icon_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    
    def color_display(self, obj):
        """Affiche la couleur avec un carré coloré"""
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border-radius: 3px;"></div>',
            obj.color
        )
    color_display.short_description = 'Couleur'
    
    def icon_display(self, obj):
        """Affiche l'icône"""
        return format_html('<i class="{}"></i>', obj.icon)
    icon_display.short_description = 'Icône'
