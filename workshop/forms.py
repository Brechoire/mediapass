"""Formulaires pour la gestion des ateliers."""

import logging
from uuid import uuid4

from django import forms
from django.db import transaction

from app.validators import (
    validate_image_content,
    validate_image_extension,
    validate_image_size,
)
from .conflicts import conflict_message, find_workshop_conflicts
from .images import optimize_workshop_image
from .models import Location, Workshop
from .naming import normalize_workshop_name, resolve_workshop_name
from .recurrence import (
    MAX_RECURRENCE_COUNT,
    RECURRENCE_CHOICES,
    RECURRENCE_NONE,
    occurrence_dates,
)

logger = logging.getLogger(__name__)


def _delete_old_image(old_image):
    """Supprime un ancien fichier image sans bloquer l'enregistrement."""
    try:
        old_image.close()
    except Exception:
        pass
    try:
        old_image.delete(save=False)
    except Exception:
        logger.exception(
            "Impossible de supprimer l'ancienne image %s",
            old_image.name,
        )


class WorkshopForm(forms.ModelForm):
    """Définir les informations d'un atelier.

    Définissez toutes les informations d'un atelier, y compris les dates,
    heures, lieu et autres paramètres.
    """

    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "list": "workshop-name-options",
                "autocomplete": "off",
                "placeholder": "Choisir ou saisir un nom d'atelier",
            }
        ),
        label="Nom de l'atelier",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=forms.Select(),
        label="Lieu",
        empty_label="Sélectionner un lieu…",
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date de début",
    )
    date_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date de fin (plusieurs jours)",
        help_text="Laisser vide si l'atelier dure une seule journée.",
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Heure de début",
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Heure de fin",
    )
    recurrence = forms.ChoiceField(
        required=False,
        choices=RECURRENCE_CHOICES,
        initial=RECURRENCE_NONE,
        widget=forms.Select(),
        label="Répétition",
        help_text=(
            "Créer plusieurs ateliers indépendants aux mêmes horaires. "
            "La première occurrence reprend la date de début ci-dessus."
        ),
    )
    recurrence_count = forms.IntegerField(
        required=False,
        initial=2,
        min_value=2,
        max_value=MAX_RECURRENCE_COUNT,
        widget=forms.NumberInput(attrs={"min": 2, "max": MAX_RECURRENCE_COUNT}),
        label="Nombre d'occurrences",
        help_text=(
            f"Entre 2 et {MAX_RECURRENCE_COUNT} occurrences. "
            "La date de fin éventuelle est décalée d'autant."
        ),
    )
    number_registered = forms.IntegerField(
        required=False,
        initial=0,
        min_value=0,
        widget=forms.NumberInput(),
        label="Nombre d'inscrits",
    )
    number_attendees = forms.IntegerField(
        required=False,
        initial=0,
        min_value=0,
        widget=forms.NumberInput(),
        label="Nombre de présents (après l'atelier)",
    )
    class_welcome = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(),
        label="Accueil de classe ?",
    )
    is_all_ages = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(),
        label="Tout public",
        help_text="Cochez si l'atelier est ouvert à tous les âges.",
    )
    min_age = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
        widget=forms.HiddenInput(),
        label="Âge minimum",
    )
    max_age = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
        widget=forms.HiddenInput(),
        label="Âge maximum",
    )
    poster_required = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(),
        label="Demander une affiche ?",
    )
    observations = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Notes internes / consignes",
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(),
        label="Visuel existant (facultatif)",
    )
    DELETE = forms.BooleanField(
        required=False,
        label="Supprimer l'image actuelle",
    )

    def __init__(self, *args, **kwargs):
        """Prépare les attributs d'accessibilité et le champ image."""
        super().__init__(*args, **kwargs)
        image_field = self.fields.get("image")
        if image_field:
            image_field.widget.attrs["accept"] = ".png,.jpg,.jpeg,.gif,.webp"
            image_field.help_text = (
                "PNG, JPG, GIF ou WebP, 5 Mo maximum. Les grandes images "
                "sont automatiquement redimensionnées."
            )
            image_field.label = (
                "Visuel existant (facultatif)"
                if self.instance.pk
                else "Affiche / visuel (facultatif)"
            )
        location_field = self.fields.get("location")
        if location_field:
            location_field.label_from_instance = lambda obj: (
                f"{obj.name} — {obj.city}" if obj.city else obj.name
            )
        name_field = self.fields.get("name")
        if name_field:
            name_field.help_text = (
                "Nom existant ou nouveau nom, ajouté automatiquement à la "
                "liste. La casse, les accents et la ponctuation sont "
                "normalisés."
            )
        for name, field in self.fields.items():
            field_id = f"id_{name}"
            described_by = []
            if field.help_text:
                described_by.append(f"{field_id}_help")
            described_by.append(f"{field_id}_error")
            field.widget.attrs["aria-describedby"] = " ".join(described_by)
            if field.required:
                field.widget.attrs["aria-required"] = "true"

    def clean(self):
        """Vérifie les conflits et prépare une éventuelle série."""
        cleaned_data = super().clean()
        location = cleaned_data.get("location")
        date_value = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if not all((location, date_value, start_time, end_time)):
            return cleaned_data

        candidate = Workshop(
            pk=self.instance.pk,
            location=location,
            date=date_value,
            date_end=cleaned_data.get("date_end"),
            start_time=start_time,
            end_time=end_time,
        )

        if self.instance.pk:
            previous = (
                Workshop.objects.only(
                    "location_id",
                    "date",
                    "date_end",
                    "start_time",
                    "end_time",
                )
                .filter(pk=self.instance.pk)
                .first()
            )
            if previous and all(
                (
                    previous.location_id == candidate.location_id,
                    previous.date == candidate.date,
                    (previous.date_end or previous.date)
                    == (candidate.date_end or candidate.date),
                    previous.start_time == candidate.start_time,
                    previous.end_time == candidate.end_time,
                )
            ):
                # On autorise la modification des autres champs d'un
                # atelier déjà en conflit sans revalider son créneau.
                return cleaned_data

        conflicts = find_workshop_conflicts(candidate)
        if conflicts:
            raise forms.ValidationError(conflict_message(conflicts))
        self._validate_recurrence(cleaned_data)
        self._validate_age_range(cleaned_data)
        return cleaned_data

    def _validate_age_range(self, cleaned_data):
        """Vérifie la tranche d'âge (miroir des ateliers médiathèque)."""
        is_all_ages = cleaned_data.get("is_all_ages")
        min_age = cleaned_data.get("min_age")
        max_age = cleaned_data.get("max_age")
        if is_all_ages:
            cleaned_data["min_age"] = None
            cleaned_data["max_age"] = None
            return
        if min_age is None and max_age is None:
            raise forms.ValidationError(
                "Veuillez spécifier au moins un âge minimum ou maximum."
            )
        if min_age is not None and max_age is not None and min_age > max_age:
            raise forms.ValidationError(
                "L'âge minimum ne peut pas être supérieur à l'âge maximum."
            )

    def _validate_recurrence(self, cleaned_data):
        """Vérifie que toutes les occurrences d'une série sont libres."""
        self._occurrence_plan = None
        recurrence = cleaned_data.get("recurrence") or RECURRENCE_NONE
        if self.instance.pk or recurrence == RECURRENCE_NONE:
            return
        if "recurrence_count" in self.errors:
            return
        count = cleaned_data.get("recurrence_count")
        if not count:
            self.add_error(
                "recurrence_count",
                "Indiquez le nombre d'occurrences à créer.",
            )
            return

        plan = occurrence_dates(
            cleaned_data.get("date"),
            cleaned_data.get("date_end"),
            recurrence,
            count,
        )
        self._occurrence_plan = plan

        for (start_a, end_a), (start_b, _end_b) in zip(plan, plan[1:]):
            if start_b <= (end_a or start_a):
                raise forms.ValidationError(
                    "La durée de l'atelier chevauche l'occurrence "
                    f"suivante ({start_b:%d/%m/%Y}). Réduisez la date de "
                    "fin ou espacez la répétition."
                )

        conflicts = []
        for index, (occurrence_start, occurrence_end) in enumerate(plan):
            if index == 0:
                # La première occurrence a déjà été contrôlée.
                continue
            candidate = Workshop(
                location=cleaned_data.get("location"),
                date=occurrence_start,
                date_end=occurrence_end,
                start_time=cleaned_data.get("start_time"),
                end_time=cleaned_data.get("end_time"),
            )
            for other in find_workshop_conflicts(candidate):
                conflicts.append((occurrence_start, other))

        if conflicts:
            details = "; ".join(
                f"le {occurrence:%d/%m/%Y} avec « {other.name} »"
                for occurrence, other in conflicts[:5]
            )
            suffix = "…" if len(conflicts) > 5 else ""
            raise forms.ValidationError(
                "La série entre en conflit avec un atelier existant : "
                f"{details}{suffix}."
            )

    def has_recurrence(self):
        """Indique si le formulaire crée plusieurs occurrences."""
        return len(self.get_occurrence_dates()) > 1

    def get_occurrence_dates(self):
        """Retourne les couples (date de début, date de fin) à créer."""
        start = self.cleaned_data.get("date")
        if self.instance.pk or not start:
            return [(start, self.cleaned_data.get("date_end"))]
        return occurrence_dates(
            start,
            self.cleaned_data.get("date_end"),
            self.cleaned_data.get("recurrence") or RECURRENCE_NONE,
            self.cleaned_data.get("recurrence_count"),
        )

    def clean_is_all_ages(self):
        """Champ absent (anciens envois) = Tout public par défaut."""
        if "is_all_ages" not in (self.data or {}):
            return True
        return self.cleaned_data.get("is_all_ages")

    def clean_number_registered(self):
        """Ramène un champ vide à zéro."""
        return self.cleaned_data.get("number_registered") or 0

    def clean_number_attendees(self):
        """Ramène un champ vide à zéro."""
        return self.cleaned_data.get("number_attendees") or 0

    def clean_image(self):
        """Valide puis optimise l'image téléversée."""
        image = self.files.get("image")
        if image:
            validate_image_extension(image)
            validate_image_size(image)
            validate_image_content(image)
            return optimize_workshop_image(image)
        return self.cleaned_data.get("image")

    def clean_name(self):
        """Nettoie le nom et refuse une valeur sans contenu utile."""
        name = " ".join((self.cleaned_data.get("name") or "").split())
        if not normalize_workshop_name(name):
            raise forms.ValidationError(
                "Le nom doit contenir au moins une lettre ou un chiffre."
            )
        return name

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
            "is_all_ages",
            "min_age",
            "max_age",
            "observations",
            "DELETE",
        )

    def save(self, commit=True, user=None):
        """Sauvegarde l'atelier avec le nom canonique de la liste."""
        workshop = super().save(commit=False)
        catalog = resolve_workshop_name(self.cleaned_data["name"])
        workshop.name = catalog.name
        if user is not None:
            if not workshop.pk:
                workshop.created_by = user
            workshop.updated_by = user
        new_image = self.files.get("image")
        delete_image = self.cleaned_data.get("DELETE")

        old_image = None
        if commit and workshop.pk and (new_image or delete_image):
            try:
                old_image = Workshop.objects.only("image").get(pk=workshop.pk).image
            except Workshop.DoesNotExist:
                old_image = None

        if delete_image and not new_image:
            for image in (
                self.cleaned_data.get("image"),
                workshop.image,
            ):
                if image:
                    try:
                        image.close()
                    except Exception:
                        pass
            workshop.image = None

        if commit:
            workshop.save()
            self.save_m2m()
            if (
                old_image
                and old_image.name
                and (not workshop.image or old_image.name != workshop.image.name)
            ):
                transaction.on_commit(lambda: _delete_old_image(old_image))
        return workshop

    def save_series(self, user=None):
        """Crée l'atelier puis toutes les occurrences de la série."""
        plan = self.get_occurrence_dates()
        with transaction.atomic():
            first = self.save(commit=True, user=user)
            if len(plan) <= 1:
                return [first]

            series_id = uuid4()
            first.series = series_id
            first.series_index = 1
            first.save(update_fields=["series", "series_index", "updated_at"])

            created = [first]
            for index, (start, end) in enumerate(plan[1:], start=2):
                clone = Workshop(
                    location=first.location,
                    name=first.name,
                    date=start,
                    date_end=end,
                    start_time=first.start_time,
                    end_time=first.end_time,
                    series=series_id,
                    series_index=index,
                    poster_required=first.poster_required,
                    number_registered=first.number_registered,
                    number_attendees=first.number_attendees,
                    class_welcome=first.class_welcome,
                    is_all_ages=first.is_all_ages,
                    min_age=first.min_age,
                    max_age=first.max_age,
                    instagram=first.instagram,
                    facebook=first.facebook,
                    mail=first.mail,
                    portail=first.portail,
                    vdn=first.vdn,
                    observations=first.observations,
                    created_by=user,
                    updated_by=user,
                )
                clone.save()
                created.append(clone)
            return created


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
    color = forms.RegexField(
        regex=r"^#[0-9A-Fa-f]{6}$",
        widget=forms.TextInput(attrs={"class": "form-control", "type": "color"}),
        label="Couleur (vue trimestrielle)",
        help_text="Ex. #ec4899 pour le rose (Anor).",
        initial="#4a6fa5",
        required=False,
    )

    class Meta:
        """Configurez le formulaire."""

        model = Location
        fields = ("name", "address", "zip_code", "city", "color")

    def clean_color(self):
        """Ramène une couleur vide vers le bleu par défaut."""
        return self.cleaned_data.get("color") or "#4a6fa5"

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
            raise forms.ValidationError("Le nom doit contenir au moins 3 caractères.")
        return data


class WorkshopPosterForm(forms.ModelForm):
    """Gérer l'affiche d'un atelier.

    Ajouter ou modifier l'affiche (visuel) d'un atelier.
    """

    DELETE = forms.BooleanField(required=False, label="Supprimer l'image actuelle")
    image = forms.ImageField(
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": ".png,.jpg,.jpeg,.gif,.webp",
            }
        ),
        required=False,
        label="Affiche",
    )

    class Meta:
        """Configurez le formulaire."""

        model = Workshop
        fields = (
            "image",
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
        """Valide puis optimise l'image téléversée."""
        image = self.files.get("image")
        if image:
            validate_image_extension(image)
            validate_image_size(image)
            validate_image_content(image)
            return optimize_workshop_image(image)
        return self.cleaned_data.get("image")

    def save(self, commit=True):
        """Sauvegarde l'affiche et supprime l'ancienne image si besoin."""
        workshop = super().save(commit=False)
        new_image = self.files.get("image")
        delete_image = self.cleaned_data.get("DELETE")

        old_image = None
        if commit and workshop.pk and (new_image or delete_image):
            try:
                old_image = Workshop.objects.only("image").get(pk=workshop.pk).image
            except Workshop.DoesNotExist:
                old_image = None

        if delete_image and not new_image:
            for image in (
                self.cleaned_data.get("image"),
                workshop.image,
            ):
                if image:
                    try:
                        image.close()
                    except Exception:
                        pass
            workshop.image = None

        if commit:
            workshop.save()
            self.save_m2m()
            if (
                old_image
                and old_image.name
                and (not workshop.image or old_image.name != workshop.image.name)
            ):
                transaction.on_commit(lambda: _delete_old_image(old_image))
        return workshop


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

    # Classes du design system du site (cf. workshop_stats.html) : la
    # classe Bootstrap "form-control" n'est définie nulle part.
    WIDGET_ATTRS = {
        "class": (
            "w-full bg-white border border-[#dce3ef] rounded-lg px-3 py-2 "
            "text-sm text-slate-900 focus:outline-none focus:ring-2 "
            "focus:ring-[#4a6fa5]/30 focus:border-[#4a6fa5]"
        )
    }

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                **WIDGET_ATTRS,
                "placeholder": "Rechercher par nom…",
            }
        ),
        label="Recherche",
    )
    location = forms.ModelChoiceField(
        required=False,
        queryset=Location.objects.all(),
        widget=forms.Select(attrs=dict(WIDGET_ATTRS)),
        label="Lieu",
        empty_label="Tous",
    )
    city = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs=dict(WIDGET_ATTRS)),
        label="Ville",
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", **WIDGET_ATTRS}),
        label="Date du",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", **WIDGET_ATTRS}),
        label="Date au",
    )
    class_welcome = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs=dict(WIDGET_ATTRS)),
        label="Accueil classe",
    )
    poster_required = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs=dict(WIDGET_ATTRS)),
        label="Affiche requise",
    )
    has_image = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs=dict(WIDGET_ATTRS)),
        label="Affiche présente",
    )
    poster_valide = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Oui"), ("no", "Non")],
        widget=forms.Select(attrs=dict(WIDGET_ATTRS)),
        label="Affiche validée",
    )
    number_registered_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={**WIDGET_ATTRS, "placeholder": "Min"}),
        label="Inscrits (min)",
    )
    number_registered_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={**WIDGET_ATTRS, "placeholder": "Max"}),
        label="Inscrits (max)",
    )
    number_attendees_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={**WIDGET_ATTRS, "placeholder": "Min"}),
        label="Présents (min)",
    )
    number_attendees_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={**WIDGET_ATTRS, "placeholder": "Max"}),
        label="Présents (max)",
    )

    def __init__(self, *args, **kwargs):
        """Initialise le formulaire avec la liste dynamique des villes."""
        super().__init__(*args, **kwargs)
        cities = (
            Location.objects.values_list("city", flat=True).distinct().order_by("city")
        )
        self.fields["city"].choices = [("", "Toutes")] + [(c, c) for c in cities]


class WorkshopStatsFilterForm(forms.Form):
    """Formulaire de filtrage pour la page /atelier-stats.

    Utilisé en GET pour permettre le bookmarking et le partage des URLs
    filtrées. Les valeurs invalides retombent sur les défauts sans 500.
    """

    year = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Année",
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
    class_welcome = forms.ChoiceField(
        required=False,
        choices=[("", "Tous"), ("yes", "Accueils"), ("no", "Classiques")],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Type",
    )
    month = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + [(str(m), f"{m:02d}") for m in range(1, 13)],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Mois",
    )
    channel = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Tous"),
            ("instagram", "Instagram"),
            ("facebook", "Facebook"),
            ("mail", "Mail"),
            ("portail", "Portail"),
            ("vdn", "VDN"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Canal",
    )
    weekday = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Tous"),
            ("2", "Lundi"),
            ("3", "Mardi"),
            ("4", "Mercredi"),
            ("5", "Jeudi"),
            ("6", "Vendredi"),
            ("7", "Samedi"),
            ("1", "Dimanche"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Jour",
    )
    slot = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Tous"),
            ("matin", "Matin (<12h)"),
            ("am", "Après-midi (12-17h)"),
            ("soir", "Soir (≥17h)"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Créneau",
    )

    def __init__(self, *args, **kwargs):
        """Initialise les choix dynamiques d'années et de villes."""
        available_years = kwargs.pop("available_years", [])
        super().__init__(*args, **kwargs)
        self.fields["year"].widget.choices = [(y, str(y)) for y in available_years]
        cities = (
            Location.objects.values_list("city", flat=True).distinct().order_by("city")
        )
        self.fields["city"].choices = [("", "Toutes")] + [(c, c) for c in cities]
