import json

from django import forms
from django.utils import timezone
from django.db.models import Q
from .models import Workshop, WorkshopParticipant, RecurrencePattern
from visitor_tracking.models import Location as VisitorLocation


class WorkshopForm(forms.ModelForm):
    is_single_day = forms.BooleanField(
        required=False,
        initial=True,
        label="Atelier sur une seule journée",
    )

    age_range_display = forms.CharField(
        required=False, widget=forms.HiddenInput(), label="Tranche d'âge sélectionnée"
    )

    class Meta:
        model = Workshop
        fields = [
            "title",
            "description",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "location",
            "max_participants",
            "poster",
            "is_all_ages",
            "min_age",
            "max_age",
            "newsletter",
            "is_class_welcome",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "placeholder": "Ex: Atelier de Lecture pour Enfants",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all resize-y min-h-[100px]",
                    "rows": 4,
                    "placeholder": "Description détaillée de l'atelier...",
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "type": "date",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "type": "date",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "type": "time",
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "type": "time",
                }
            ),
            "location": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                }
            ),
            "max_participants": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "min": 1,
                    "max": 100,
                }
            ),
            "poster": forms.FileInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[#e8eef7] file:text-[#4a6fa5] hover:file:bg-[#dce3ef] transition-all",
                    "accept": "image/*",
                }
            ),
            "is_all_ages": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 rounded border-gray-300 text-[#4a6fa5] focus:ring-[#4a6fa5]"
                }
            ),
            "min_age": forms.HiddenInput(),
            "max_age": forms.HiddenInput(),
            "newsletter": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 rounded border-gray-300 text-[#4a6fa5] focus:ring-[#4a6fa5]"
                }
            ),
            "is_class_welcome": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 rounded border-gray-300 text-[#4a6fa5] focus:ring-[#4a6fa5]"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Titre de l'atelier"
        self.fields["description"].label = "Description"
        self.fields["start_date"].label = "Date de début"
        self.fields["end_date"].label = "Date de fin"
        self.fields["start_time"].label = "Heure de début"
        self.fields["end_time"].label = "Heure de fin"
        self.fields["location"].label = "Lieu"
        self.fields["location"].empty_label = "Sélectionnez un lieu..."
        qs = VisitorLocation.objects.filter(is_active=True)
        if user and not user.is_superuser:
            qs = qs.filter(user=user)
        self.fields["location"].queryset = qs.order_by("order", "name")
        self.fields["max_participants"].label = "Nombre maximum de participants"
        self.fields["poster"].label = "Affiche de l'atelier"
        self.fields["is_all_ages"].label = "Tout public"
        self.fields["min_age"].label = "Âge minimum"
        self.fields["max_age"].label = "Âge maximum"
        self.fields["newsletter"].label = "Newsletter"
        self.fields["is_class_welcome"].label = "Accueil de classe"

        self.fields["end_date"].help_text = (
            "Laissez vide si l'atelier se déroule sur une seule journée"
        )
        self.fields["max_participants"].help_text = (
            "Nombre maximum de participants autorisés"
        )
        self.fields["poster"].help_text = (
            "Image de l'affiche de l'atelier (format: JPG, PNG)"
        )
        self.fields["is_all_ages"].help_text = (
            "Cochez si l'atelier est ouvert à tous les âges"
        )
        self.fields["newsletter"].help_text = (
            "Cochez pour envoyer une newsletter pour cet atelier"
        )
        self.fields["is_class_welcome"].help_text = (
            "Cochez si cet atelier peut accueillir des classes"
        )

    def clean_start_date(self):
        start_date = self.cleaned_data.get("start_date")
        if start_date and start_date < timezone.now().date():
            raise forms.ValidationError(
                "La date de début ne peut pas être dans le passé."
            )
        return start_date

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        is_single_day = cleaned_data.get("is_single_day")
        is_all_ages = cleaned_data.get("is_all_ages")
        min_age = cleaned_data.get("min_age")
        max_age = cleaned_data.get("max_age")

        if is_single_day:
            cleaned_data["end_date"] = None
        elif end_date and start_date and end_date < start_date:
            raise forms.ValidationError(
                "La date de fin ne peut pas être antérieure à la date de début."
            )

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "L'heure de fin doit être postérieure à l'heure de début."
            )

        if not is_all_ages:
            if min_age is None and max_age is None:
                raise forms.ValidationError(
                    "Veuillez spécifier au moins un âge minimum ou maximum."
                )

            if min_age is not None and max_age is not None and min_age > max_age:
                raise forms.ValidationError(
                    "L'âge minimum ne peut pas être supérieur à l'âge maximum."
                )
        else:
            cleaned_data["min_age"] = None
            cleaned_data["max_age"] = None

        return cleaned_data


class QuickLocationForm(forms.Form):
    """Formulaire rapide pour créer un lieu depuis le modal HTMX"""

    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "placeholder": "Ex: Médiathèque, Ludothèque...",
                "autofocus": True,
            }
        ),
        label="Nom du lieu",
    )

    icon = forms.ChoiceField(
        choices=[
            ("bx-building", "🏢 Bâtiment"),
            ("bx-book", "📚 Livre"),
            ("bx-movie", "🎬 Cinéma"),
            ("bx-music", "🎵 Musique"),
            ("bx-paint", "🎨 Peinture"),
            ("bx-game", "🎮 Jeu"),
            ("bx-child", "🧒 Enfant"),
            ("bx-group", "👥 Groupe"),
        ],
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2220%22%20height%3D%2220%22%20fill%3D%22none%22%20stroke%3D%22%23b0bedb%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_0.75rem_center] bg-[length:1.25rem]",
            }
        ),
        label="Icône",
        initial="bx-building",
    )

    color = forms.ChoiceField(
        choices=[
            ("#4F46E5", "Indigo"),
            ("#3B82F6", "Bleu"),
            ("#06B6D4", "Cyan"),
            ("#10B981", "Vert"),
            ("#F59E0B", "Ambre"),
            ("#EF4444", "Rouge"),
            ("#EC4899", "Rose"),
            ("#8B5CF6", "Violet"),
        ],
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2220%22%20height%3D%2220%22%20fill%3D%22none%22%20stroke%3D%22%23b0bedb%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_0.75rem_center] bg-[length:1.25rem]",
            }
        ),
        label="Couleur",
        initial="#4F46E5",
    )


class WorkshopParticipantForm(forms.ModelForm):
    class Meta:
        model = WorkshopParticipant
        fields = ["first_name", "last_name", "age", "email", "phone", "status", "notes"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "placeholder": "Prénom",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "placeholder": "Nom",
                }
            ),
            "age": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "min": 0,
                    "max": 120,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "placeholder": "email@exemple.com",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                    "placeholder": "06 12 34 56 78",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2220%22%20height%3D%2220%22%20fill%3D%22none%22%20stroke%3D%22%23b0bedb%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_0.75rem_center] bg-[length:1.25rem]"
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all resize-y min-h-[80px]",
                    "rows": 3,
                    "placeholder": "Notes supplémentaires...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Prénom"
        self.fields["last_name"].label = "Nom"
        self.fields["age"].label = "Âge"
        self.fields["email"].label = "Email"
        self.fields["phone"].label = "Téléphone"
        self.fields["status"].label = "Statut"
        self.fields["notes"].label = "Notes"
        self.fields["email"].help_text = "Optionnel"
        self.fields["phone"].help_text = "Optionnel"
        self.fields["notes"].help_text = (
            "Informations supplémentaires sur le participant"
        )


class WorkshopGroupReservationForm(forms.Form):
    leader_first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "placeholder": "Prénom du responsable",
            }
        ),
        label="Prénom du responsable *",
    )

    leader_last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "placeholder": "Nom du responsable",
            }
        ),
        label="Nom du responsable *",
    )

    leader_age = forms.IntegerField(
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all"
            }
        ),
        label="Âge du responsable *",
    )

    leader_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "placeholder": "email@exemple.com",
            }
        ),
        label="Email du responsable",
    )

    leader_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "placeholder": "06 12 34 56 78",
            }
        ),
        label="Téléphone du responsable",
    )

    group_size = forms.IntegerField(
        min_value=2,
        max_value=10,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "min": 2,
                "max": 10,
            }
        ),
        label="Nombre total de personnes *",
        help_text="Incluant le responsable (2-10 personnes)",
    )

    additional_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all resize-y min-h-[80px]",
                "rows": 3,
                "placeholder": "Informations sur les autres membres du groupe...",
            }
        ),
        label="Informations sur le groupe",
        help_text="Âges, noms des autres membres, besoins particuliers...",
    )

    status = forms.ChoiceField(
        choices=WorkshopParticipant.STATUS_CHOICES,
        initial="confirmed",
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2220%22%20height%3D%2220%22%20fill%3D%22none%22%20stroke%3D%22%23b0bedb%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_0.75rem_center] bg-[length:1.25rem]"
            }
        ),
        label="Statut",
    )

    def __init__(self, *args, **kwargs):
        workshop = kwargs.pop("workshop", None)
        super().__init__(*args, **kwargs)

        if workshop and workshop.is_full:
            self.fields["status"].initial = "waiting"
            self.fields["status"].widget.attrs["disabled"] = "disabled"

        self.fields["leader_email"].help_text = "Optionnel"
        self.fields["leader_phone"].help_text = "Optionnel"

    def clean_group_size(self):
        group_size = self.cleaned_data.get("group_size")
        if group_size < 2:
            raise forms.ValidationError(
                "Un groupe doit comporter au moins 2 personnes."
            )
        if group_size > 10:
            raise forms.ValidationError("Un groupe ne peut pas dépasser 10 personnes.")
        return group_size


class WorkshopSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] placeholder:text-[#b0bedb] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "placeholder": "Rechercher un atelier...",
            }
        ),
        label="Recherche",
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "type": "date",
            }
        ),
        label="À partir du",
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm text-[#1e293b] focus:outline-none focus:ring-2 focus:ring-[#4a6fa5]/20 focus:border-[#4a6fa5] transition-all",
                "type": "date",
            }
        ),
        label="Jusqu'au",
    )


class RecurrenceForm(forms.ModelForm):
    """Formulaire de configuration de la récurrence"""

    class Meta:
        model = RecurrencePattern
        fields = [
            "frequency",
            "interval",
            "days_of_week",
            "period_start",
            "period_end",
            "excluded_dates",
            "month_day",
        ]
        widgets = {
            "period_start": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm",
                }
            ),
            "period_end": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm",
                }
            ),
            "days_of_week": forms.HiddenInput(),
            "excluded_dates": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["frequency"].label = "Fréquence"
        self.fields["frequency"].widget.attrs = {
            "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm"
        }
        self.fields["interval"].label = "Toutes les X semaines"
        self.fields["interval"].initial = 2
        self.fields["interval"].widget.attrs = {
            "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm w-20",
            "min": 1,
            "max": 12,
        }
        self.fields["period_start"].label = "Date de début"
        self.fields["period_end"].label = "Date de fin"
        self.fields["month_day"].label = "Jour du mois"
        self.fields["month_day"].widget.attrs = {
            "class": "w-full px-4 py-2.5 border border-[#dce3ef] rounded-xl text-sm w-20",
            "min": 1,
            "max": 31,
        }

    def clean_days_of_week(self):
        val = self.cleaned_data.get("days_of_week")
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []
        return val or []

    def clean_excluded_dates(self):
        val = self.cleaned_data.get("excluded_dates")
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []
        return val or []

    def clean(self):
        cleaned = super().clean()
        freq = cleaned.get("frequency")
        days = cleaned.get("days_of_week")

        weekly_freqs = ("weekly", "biweekly", "every_3_weeks")
        if freq in weekly_freqs:
            if not days:
                raise forms.ValidationError(
                    "Sélectionnez au moins un jour de la semaine."
                )

        if freq in ("monthly", "every_2_months"):
            if not cleaned.get("month_day"):
                raise forms.ValidationError("Indiquez le jour du mois (1-31).")

        if not cleaned.get("period_start"):
            raise forms.ValidationError("La date de début est requise.")
        if not cleaned.get("period_end"):
            raise forms.ValidationError("La date de fin est requise.")
        if (
            cleaned.get("period_start")
            and cleaned.get("period_end")
            and cleaned["period_end"] < cleaned["period_start"]
        ):
            raise forms.ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )

        return cleaned
