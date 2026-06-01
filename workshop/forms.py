"""Formulaires pour la gestion des ateliers."""

from django import forms
from django.core.exceptions import ValidationError

from .models import Location, Workshop


class WorkshopForm(forms.ModelForm):
    """Définir les informations d'un atelier.

    Définissez toutes les informations d'un atelier, y compris les dates,
    heures, lieu et autres paramètres.
    """

    name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Nom de l'atelier",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Lieu",
    )
    date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        label="Date de début",
    )
    date_end = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        label="Date de fin",
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        label="Heure de début",
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "form-control"}
        ),
        label="Heure de fin",
    )
    number_registered = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Nombre de participants",
    )
    number_attendees = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Nombre d'inscription",
    )
    class_welcome = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Accueil de classe ?",
    )
    poster_required = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Affiche requis ?",
    )
    observations = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        label="Observations",
    )

    class Meta:
        """Configurez le formulaire."""

        model = Workshop
        fields = (
            "name",
            "date",
            "date_end",
            "start_time",
            "end_time",
            "poster_required",
            "image",
            "location",
            "number_registered",
            "number_attendees",
            "class_welcome",
            "observations",
        )


class LocationForm(forms.ModelForm):
    """Définir les informations d'un lieu.

    Définissez les informations d'un lieu où se déroulent les ateliers.
    """

    name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Nom du lieu",
    )
    address = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Adresse",
    )
    zip_code = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Code postal",
    )
    city = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Ville",
    )

    class Meta:
        """Configurez le formulaire."""

        model = Location
        fields = ("name", "address", "zip_code", "city")

    def clean_name(self):
        """Validez le nom du lieu.

        Effectue les validations suivantes :
        - Longueur minimale de 3 caractères
        - Unicité du nom dans la base de données

        Returns:
            str: Le nom validé.

        Raises:
            ValidationError: Si le nom est invalide.
        """
        data = self.cleaned_data["name"]
        if len(data) < 3:
            raise forms.ValidationError(
                "Le nom doit contenir au moins 3 caractères."
            )
        return data


class WorkshopPosterForm(forms.ModelForm):
    """Gérer l'affiche d'un atelier.

    Ajouter ou modifier l'affiche d'un atelier et gérer sa diffusion
    sur différents canaux.
    """

    DELETE = forms.BooleanField(
        required=False, label="Supprimer l'image actuelle"
    )
    image = forms.ImageField(
        widget=forms.FileInput(attrs={"class": "form-control"}),
        required=False,
        label="Affiche",
    )
    facebook = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        required=False,
        label="Facebook",
    )
    instagram = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        required=False,
        label="Instagram",
    )
    mail = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        required=False,
        label="Mail",
    )
    portail = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        required=False,
        label="Portail",
    )
    vdn = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        required=False,
        label="VDN",
    )

    class Meta:
        """Configurez le formulaire."""

        model = Workshop
        fields = (
            "image",
            "facebook",
            "instagram",
            "mail",
            "portail",
            "vdn",
            "DELETE",
        )

    def __init__(self, *args, **kwargs):
        """Initialisez le formulaire.

        Args:
            *args: Arguments positionnels.
            **kwargs: Arguments nommés, dont 'request'.
        """
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """Validez les données du formulaire.

        Validez les données pour vous assurer qu'elles sont cohérentes.

        Returns:
            dict: Les données validées.

        Raises:
            ValidationError: Si les données sont invalides.
        """
        cleaned_data = super().clean()
        user = self.request.user
        if user.groups.filter(name="communication").exists():
            if "poster_valide" in cleaned_data:
                del cleaned_data["poster_valide"]
        return cleaned_data

    def clean_image(self):
        """Validez l'image téléchargée.

        Effectue les validations suivantes :
        - Taille maximale autorisée
        - Format de fichier supporté

        Returns:
            ImageField: L'image validée.
        """
        image = self.cleaned_data.get("image")
        if image:
            max_size = 5 * 1024 * 1024  # 5 MB
            if image.size > max_size:
                raise ValidationError(
                    "Le fichier dépasse la taille maximale autorisée de 5MB."
                )
        return image


class WorkshopPosterValidationForm(forms.ModelForm):
    """Validez l'affiche d'un atelier.

    Validez ou rejetez une affiche avec des commentaires.
    """

    description_poster_valide = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control"}),
        label="Commentaire",
    )

    class Meta:
        """Configurez le formulaire."""

        model = Workshop
        fields = ("description_poster_valide",)


class WorkshopFilterForm(forms.Form):
    """Formulaire de filtrage pour la liste des ateliers.

    Tous les champs sont optionnels. Utilisé en GET pour permettre
    le bookmarking et le partage des URLs filtrées.
    """

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Rechercher par nom…",
            }
        ),
        label="Recherche",
    )
    location = forms.ModelChoiceField(
        required=False,
        queryset=Location.objects.all(),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Lieu",
        empty_label="Tous",
    )
    city = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Ville",
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        label="Date du",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"}
        ),
        label="Date au",
    )
    class_welcome = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Accueil classe",
    )
    poster_required = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Affiche requise",
    )
    has_image = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Affiche présente",
    )
    poster_valide = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Affiche validée",
    )
    number_registered_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Min"}
        ),
        label="Inscrits (min)",
    )
    number_registered_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Max"}
        ),
        label="Inscrits (max)",
    )
    number_attendees_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Min"}
        ),
        label="Présents (min)",
    )
    number_attendees_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Max"}
        ),
        label="Présents (max)",
    )

    def __init__(self, *args, **kwargs):
        """Initialise le formulaire avec la liste dynamique des villes."""
        super().__init__(*args, **kwargs)
        cities = (
            Location.objects.values_list("city", flat=True)
            .distinct()
            .order_by("city")
        )
        self.fields["city"].choices = [("", "Toutes")] + [
            (c, c) for c in cities
        ]
