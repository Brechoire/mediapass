"""Formulaires pour l'application shop.

Ce module définit les formulaires Django pour la gestion des catégories,
structures, produits et réservations. Il inclut la validation des données
et la personnalisation de l'affichage des formulaires.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Category, Product, Reservation, Structure


class CategoryForm(forms.ModelForm):
    """Formulaire pour la création et la modification de catégories.

    Ce formulaire permet de gérer les catégories de produits, avec un
    champ pour le nom de la catégorie.
    """

    class Meta:
        """Configuration du formulaire pour les catégories."""

        model = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "name": "Nom de la catégorie",
        }


class StructureForm(forms.ModelForm):
    """Formulaire pour la création et la modification de structures.

    Ce formulaire permet de gérer les informations complètes d'une structure,
    y compris son nom, ses coordonnées et sa couleur d'identification.
    """

    class Meta:
        """Configuration du formulaire pour les structures."""

        model = Structure
        fields = [
            "name",
            "email",
            "address",
            "city",
            "zip_code",
            "color",
            "image",
            "valid",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "zip_code": forms.TextInput(attrs={"class": "form-control"}),
            "color": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "type": "color",
                }
            ),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "valid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nom de la structure",
            "email": "Email de la structure pour validation de réservation",
            "address": "Adresse",
            "city": "Ville",
            "zip_code": "Code Postal",
            "color": "Couleur",
            "image": "Logo de la structure",
            "valid": "Valider la structure",
        }


class StructureRegisterForm(forms.ModelForm):
    """Formulaire pour l'inscription d'une nouvelle structure.

    Ce formulaire est une version simplifiée du StructureForm, sans le
    champ de couleur, destiné à l'inscription initiale d'une structure.
    """

    class Meta:
        """Configuration du formulaire d'inscription des structures."""

        model = Structure
        fields = ["name", "email", "address", "city", "zip_code"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "zip_code": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "name": "Nom de la structure",
            "email": "Email de la structure pour validation de réservation",
            "address": "Adresse",
            "city": "Ville",
            "zip_code": "Code Postal",
        }


class ProductForm(forms.ModelForm):
    """Formulaire pour la création et la modification de produits.

    Ce formulaire permet de gérer toutes les informations d'un produit,
    y compris son nom, sa quantité, sa catégorie, sa description,
    son image et son statut.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['status'].initial = True

    class Meta:
        """Configuration du formulaire pour les produits."""

        model = Product
        fields = [
            "name",
            "quantity",
            "category",
            "description",
            "image",
            "price",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            "status": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": "Nom du produit",
            "quantity": "Quantité",
            "category": "Catégorie",
            "description": "Description",
            "image": "Image",
            "price": "Prix",
            "status": "Actif",
        }


class ApprovalForm(forms.Form):
    """Formulaire pour l'approbation des réservations.

    Ce formulaire permet d'ajouter un commentaire lors de l'approbation
    ou du refus d'une réservation.
    """

    comment = forms.CharField(
        label="Commentaire (optionnel)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        required=False,
    )


class DisapprovalForm(forms.Form):
    """Formulaire pour la désapprobation des réservations.

    Ce formulaire permet de sélectionner une raison et d'ajouter un commentaire
    lors de la désapprobation d'une réservation.
    """

    REASON_CHOICES = [
        ('error', 'Erreur dans la demande'),
        ('conflict', 'Réservation en attente soumise avant celle-ci'),
        ('unavailable', 'Produit non disponible'),
        ('other', 'Autre raison'),
    ]

    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        label="Raison de désapprobation",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True
    )
    comment = forms.CharField(
        label="Commentaire (optionnel)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        required=False
    )


class ReservationForm(forms.ModelForm):
    """Formulaire pour la création et la modification de réservations.

    Ce formulaire permet de gérer les réservations de produits, avec
    validation des dates, heures et quantités demandées.
    """

    start_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "min": timezone.localdate().strftime("%Y-%m-%d"),
                "class": "form-control",
            }
        ),
        label="Date de début",
    )
    end_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "min": timezone.localdate().strftime("%Y-%m-%d"),
                "class": "form-control",
            }
        ),
        label="Date de fin",
    )
    structure = forms.ModelChoiceField(
        queryset=Structure.objects.filter(is_registered=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Structure",
    )
    quantity = forms.IntegerField(
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Quantité",
    )
    deposit_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        label="Heure de début",
    )
    pickup_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        label="Heure de fin",
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control"}),
        label="Description",
        required=False,
    )

    class Meta:
        """Configuration du formulaire pour les réservations."""

        model = Reservation
        fields = [
            "start_date",
            "deposit_time",
            "end_date",
            "pickup_time",
            "structure",
            "quantity",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """Nettoyer et valider les données du formulaire.

        Vérifie que :
        - La date de fin n'est pas antérieure à la date de début
        - La date de début n'est pas dans le passé
        - La quantité demandée est disponible
        - Aucun conflit de réservation pour ce produit aux dates demandées

        Returns:
            dict: Les données nettoyées et validées.

        Raises:
            ValidationError: Si les conditions ne sont pas respectées.
        """
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        quantity = cleaned_data.get("quantity")

        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError(
                    "La date de fin ne peut pas être antérieure à la date "
                    "de début."
                )

            if start_date < timezone.localdate():
                raise ValidationError(
                    "La date de début ne peut pas être dans le passé."
                )

            if self.product and quantity:
                if quantity > self.product.quantity:
                    raise ValidationError(
                        f"La quantité demandée ({quantity}) dépasse la "
                        f"quantité disponible ({self.product.quantity})."
                    )

        return cleaned_data
