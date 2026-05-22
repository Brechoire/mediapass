from django import forms

from .models import Kakemono, KakemonoReservation


class KakemonoForm(forms.ModelForm):
    class Meta:
        model = Kakemono
        fields = ["title", "description", "image"]
        labels = {
            "title": "Titre",
            "description": "Description",
            "image": "Image",
        }


class KakemonoReservationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajout des données d'image aux options du select
        self.fields["kakemonos"].queryset = Kakemono.objects.all().order_by(
            "title"
        )
        self.fields["kakemonos"].widget.option_attributes = lambda obj: {
            "data-image": obj.image.url if obj.image else "",
            "data-description": obj.description if obj.description else "",
        }

    kakemonos = forms.ModelMultipleChoiceField(
        queryset=None,  # Sera défini dans __init__
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select select2",
                "required": True,
                "data-placeholder": "Sélectionnez un ou plusieurs kakémonos",
            }
        ),
        help_text=(
            "Cliquez sur le champ pour afficher la liste complète des"
            " kakémonos disponibles"
        ),
    )

    class Meta:
        model = KakemonoReservation
        fields = [
            "first_name",
            "last_name",
            "kakemonos",
            "start_date",
            "end_date",
            "notes",
        ]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "kakemonos": "Kakémonos à réserver",
            "start_date": "Date de début",
            "end_date": "Date de fin",
            "notes": "Notes",
        }
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Votre prénom"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Votre nom"}
            ),
            "start_date": forms.DateInput(
                attrs={"class": "form-control flatpickr", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control flatpickr", "type": "date"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Notes additionnelles (optionnel)",
                }
            ),
        }
