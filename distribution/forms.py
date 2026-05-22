from django import forms
from django.contrib.auth.models import User
from .models import Commune, Lieu, CampagneDistribution, Distribution


class CommuneForm(forms.ModelForm):
    """Formulaire pour créer/modifier une commune"""
    
    class Meta:
        model = Commune
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la commune'
            })
        }


class LieuForm(forms.ModelForm):
    """Formulaire pour créer/modifier un lieu"""
    
    class Meta:
        model = Lieu
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du lieu'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description optionnelle du lieu'
            }),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            )
        }


class CampagneDistributionForm(forms.ModelForm):
    """Formulaire pour créer/modifier une campagne de distribution"""
    
    class Meta:
        model = CampagneDistribution
        fields = ['name', 'description', 'status', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la campagne (ex: Quinzaine du conte)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la campagne'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Formater les dates existantes pour les champs de type date
        if self.instance and self.instance.pk:
            if self.instance.start_date:
                self.initial['start_date'] = self.instance.start_date.strftime(
                    '%Y-%m-%d'
                )
            if self.instance.end_date:
                self.initial['end_date'] = self.instance.end_date.strftime(
                    '%Y-%m-%d'
                )
        else:
            # Pour les nouvelles campagnes, définir "En cours" par défaut
            self.initial['status'] = 'active'
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
        
        return cleaned_data


class DistributionForm(forms.ModelForm):
    """Formulaire pour gérer une distribution individuelle"""
    
    class Meta:
        model = Distribution
        fields = ['is_distributed', 'distributed_by', 'notes']
        widgets = {
            'is_distributed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'distributed_by': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notes optionnelles'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les utilisateurs actifs
        self.fields['distributed_by'].queryset = User.objects.filter(is_active=True)


class BulkDistributionForm(forms.Form):
    """Formulaire pour la distribution en masse"""
    
    campagne = forms.ModelChoiceField(
        queryset=CampagneDistribution.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Campagne"
    )
    
    lieux = forms.ModelMultipleChoiceField(
        queryset=Lieu.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Lieux à distribuer"
    )
    
    distributed_by = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Distribué par"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Notes communes pour tous les lieux sélectionnés'
        }),
        label="Notes"
    )


class CampagneLieuxForm(forms.Form):
    """Formulaire pour ajouter des lieux à une campagne"""
    
    lieux = forms.ModelMultipleChoiceField(
        queryset=Lieu.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Sélectionner les lieux à ajouter à la campagne"
    )
    
    def __init__(self, campagne=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if campagne:
            # Exclure les lieux déjà dans la campagne
            lieux_existants = campagne.distributions.values_list('lieu_id', flat=True)
            self.fields['lieux'].queryset = Lieu.objects.filter(
                is_active=True
            ).exclude(id__in=lieux_existants)


class SearchForm(forms.Form):
    """Formulaire de recherche pour les campagnes"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher une campagne...'
        }),
        label="Recherche"
    )
    
    status = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + CampagneDistribution.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Statut"
    )
    
    commune = forms.ModelChoiceField(
        queryset=Commune.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Commune"
    )
