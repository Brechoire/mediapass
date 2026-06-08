from datetime import date

from django import forms
from django.utils import timezone
from .models import Location, VisitorCount
from library_workshops.utils import filter_location_owned

# Tailwind CSS classes
TAILWIND_INPUT = (
    "block w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-emerald-500 focus:ring-emerald-500 sm:text-sm"
)
TAILWIND_SELECT = (
    "block w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-emerald-500 focus:ring-emerald-500 sm:text-sm"
)
TAILWIND_DATE = (
    "block w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-emerald-500 focus:ring-emerald-500 sm:text-sm"
)


class BulkVisitorCountForm(forms.Form):
    """Formulaire de saisie rétroactive pour tous les espaces"""

    date = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": TAILWIND_DATE},
            format="%Y-%m-%d",
        ),
        label="Date",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["date"].widget.attrs["type"] = "date"
        self.fields["date"].max_value = date.today()
        self.fields["date"].widget.attrs["max"] = date.today().isoformat()

        # Ajouter un champ pour chaque espace actif de l'utilisateur
        locations = filter_location_owned(
            Location.objects.filter(is_active=True), user
        ).order_by("order", "name")
        for location in locations:
            field_name = f"location_{location.id}"
            self.fields[field_name] = forms.IntegerField(
                min_value=0,
                required=False,
                initial=0,
                label=location.name,
                widget=forms.NumberInput(
                    attrs={"class": TAILWIND_INPUT, "min": "0", "placeholder": "0"}
                ),
            )

    def get_location_fields(self, user=None):
        """Retourne les champs des espaces avec leurs infos"""
        locations = filter_location_owned(
            Location.objects.filter(is_active=True), user
        ).order_by("order", "name")
        fields = []
        for location in locations:
            field_name = f"location_{location.id}"
            if field_name in self.fields:
                fields.append(
                    {
                        "field": self[field_name],
                        "location": location,
                        "name": field_name,
                    }
                )
        return fields


class DateRangeForm(forms.Form):
    """Formulaire pour filtrer par période"""

    PERIOD_CHOICES = [
        ("7_days", "7 derniers jours"),
        ("30_days", "30 derniers jours"),
        ("this_month", "Ce mois-ci"),
        ("last_month", "Mois dernier"),
        ("this_year", "Cette année"),
        ("custom", "Personnalisé"),
    ]

    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        initial="30_days",
        widget=forms.Select(attrs={"class": TAILWIND_SELECT}),
        label="Période",
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": TAILWIND_DATE}),
        label="Date début",
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": TAILWIND_DATE}),
        label="Date fin",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        empty_label="Tous les espaces",
        widget=forms.Select(attrs={"class": TAILWIND_SELECT}),
        label="Espace",
    )


class LocationForm(forms.ModelForm):
    """Formulaire pour créer/modifier un espace"""

    class Meta:
        model = Location
        fields = ["name", "description", "icon", "color", "order", "is_active"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": TAILWIND_INPUT, "placeholder": "Ex: Médiathèque"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": TAILWIND_INPUT,
                    "rows": 3,
                    "placeholder": "Description optionnelle...",
                }
            ),
            "icon": forms.TextInput(
                attrs={"class": TAILWIND_INPUT, "placeholder": "bx-building"}
            ),
            "color": forms.TextInput(attrs={"class": TAILWIND_INPUT, "type": "color"}),
            "order": forms.NumberInput(attrs={"class": TAILWIND_INPUT, "min": "0"}),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500"
                }
            ),
        }
