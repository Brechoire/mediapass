"""Formulaires de l'application newsletter."""

from django import forms

from accounts.models import LibraryProfile

from .models import (
    BORDER_STYLE_CHOICES,
    FONT_CHOICES,
    HEADER_ALIGN_CHOICES,
    HEADER_HEIGHT_CHOICES,
    RADIUS_CHOICES,
    WORKSHOP_VARIANT_CHOICES,
    Block,
    HeaderPreset,
    Newsletter,
    Section,
)


class NewsletterForm(forms.ModelForm):
    """Création d'une édition de newsletter."""

    class Meta:
        model = Newsletter
        fields = ["title", "subject", "period_start", "period_end"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-[#dce3ef] px-3 py-2 "
                    "text-sm focus:border-[#4a6fa5] focus:ring-2 "
                    "focus:ring-[#4a6fa5]/20 focus:outline-none",
                    "placeholder": "ex. Newsletter de septembre",
                }
            ),
            "subject": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-[#dce3ef] px-3 py-2 "
                    "text-sm focus:border-[#4a6fa5] focus:ring-2 "
                    "focus:ring-[#4a6fa5]/20 focus:outline-none"
                }
            ),
            "period_start": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full rounded-lg border border-[#dce3ef] px-3 py-2 "
                    "text-sm focus:border-[#4a6fa5] focus:ring-2 "
                    "focus:ring-[#4a6fa5]/20 focus:outline-none",
                },
                format="%Y-%m-%d",
            ),
            "period_end": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full rounded-lg border border-[#dce3ef] px-3 py-2 "
                    "text-sm focus:border-[#4a6fa5] focus:ring-2 "
                    "focus:ring-[#4a6fa5]/20 focus:outline-none",
                },
                format="%Y-%m-%d",
            ),
        }


class SettingsForm(forms.ModelForm):
    """Panneau « Paramètres & thème » du builder."""

    class Meta:
        model = Newsletter
        fields = [
            "title",
            "subject",
            "preheader",
            "period_start",
            "period_end",
            "primary_color",
            "background_color",
            "font_family",
            "workshop_default_variant",
            "workshop_bg_color",
            "workshop_title_color",
            "workshop_text_color",
            "workshop_border_style",
            "workshop_border_color",
            "workshop_border_width",
            "workshop_border_radius",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "nl-input"}),
            "subject": forms.TextInput(attrs={"class": "nl-input"}),
            "preheader": forms.TextInput(
                attrs={"class": "nl-input", "placeholder": "Aperçu dans la boîte mail"}
            ),
            "period_start": forms.DateInput(
                attrs={"type": "date", "class": "nl-input"}, format="%Y-%m-%d"
            ),
            "period_end": forms.DateInput(
                attrs={"type": "date", "class": "nl-input"}, format="%Y-%m-%d"
            ),
            "primary_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "background_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "font_family": forms.Select(attrs={"class": "nl-input"}),
            "workshop_default_variant": forms.RadioSelect(
                attrs={"class": "nl-variant-radio"}
            ),
            "workshop_bg_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "workshop_title_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "workshop_text_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "workshop_border_style": forms.Select(attrs={"class": "nl-input"}),
            "workshop_border_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "workshop_border_width": forms.NumberInput(
                attrs={
                    "type": "range",
                    "min": "0",
                    "max": "4",
                    "step": "1",
                    "class": "w-full accent-[#4a6fa5]",
                }
            ),
            "workshop_border_radius": forms.Select(attrs={"class": "nl-input"}),
        }

    workshop_bg_transparent = forms.BooleanField(
        label="Fond transparent",
        required=False,
        help_text="Cochez pour hériter du fond de section",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["font_family"].choices = FONT_CHOICES
        self.fields["workshop_bg_color"].required = False
        self.fields["workshop_bg_color"].help_text = "Vide = transparent"
        self.fields["workshop_title_color"].required = False
        self.fields["workshop_text_color"].required = False
        self.fields["workshop_border_color"].required = False
        self.fields["workshop_border_style"].required = False
        self.fields["workshop_border_width"].required = False
        self.fields["workshop_border_radius"].required = False
        if self.instance and not self.instance.workshop_bg_color:
            self.fields["workshop_bg_transparent"].initial = True

    def clean_primary_color(self):
        return (
            self.cleaned_data["primary_color"].lower()
            if self.cleaned_data.get("primary_color")
            else ""
        )

    def clean_background_color(self):
        v = self.cleaned_data.get("background_color", "")
        return v.lower() if v else ""

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("workshop_bg_transparent"):
            cleaned["workshop_bg_color"] = "transparent"
        else:
            v = cleaned.get("workshop_bg_color", "")
            cleaned["workshop_bg_color"] = v.lower() if v else "#ffffff"
        # map legacy "side" -> "side-left"
        if cleaned.get("workshop_default_variant") == "side":
            cleaned["workshop_default_variant"] = "side-left"
        for f in ("workshop_border_color", "workshop_title_color", "workshop_text_color"):
            v = cleaned.get(f, "")
            cleaned[f] = v.lower() if v else ""
        return cleaned


ALIGN_CHOICES = [
    ("left", "Gauche"),
    ("center", "Centré"),
    ("right", "Droite"),
]


def styled(widget_attrs):
    base = widget_attrs.get("class", "")
    widget_attrs["class"] = (
        base + " w-full rounded-lg border border-[#dce3ef] px-3 py-2 text-sm "
        "focus:border-[#4a6fa5] focus:ring-2 focus:ring-[#4a6fa5]/20 focus:outline-none"
    )
    return widget_attrs


class HeadingForm(forms.Form):
    text = forms.CharField(
        label="Titre", max_length=200, widget=forms.Textarea(attrs=styled({"rows": 2}))
    )
    align = forms.ChoiceField(label="Alignement", choices=ALIGN_CHOICES)
    size = forms.IntegerField(
        label="Taille (px)", min_value=12, max_value=60, initial=28
    )
    color = forms.CharField(
        label="Couleur", widget=forms.TextInput(attrs={"type": "color"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].initial = "#1e293b"


class TextForm(forms.Form):
    html = forms.CharField(
        label="Contenu", widget=forms.Textarea(attrs=styled({"rows": 8}))
    )
    align = forms.ChoiceField(label="Alignement", choices=ALIGN_CHOICES)
    font_size = forms.IntegerField(
        label="Taille du texte (px)",
        min_value=10,
        max_value=32,
        initial=15,
        required=False,
    )


class ButtonForm(forms.Form):
    label = forms.CharField(label="Libellé", max_length=100)
    url = forms.URLField(label="Lien")
    align = forms.ChoiceField(
        label="Alignement", choices=ALIGN_CHOICES, initial="center"
    )


class SpacerForm(forms.Form):
    height = forms.IntegerField(
        label="Hauteur (px)", min_value=4, max_value=120, initial=24
    )


class ImageForm(forms.Form):
    new_image = forms.ImageField(label="Téléverser une image", required=False)
    alt = forms.CharField(label="Texte alternatif", max_length=200, required=False)
    link = forms.URLField(label="Lien au clic", required=False)
    width = forms.ChoiceField(
        label="Largeur",
        choices=[("100", "100 %"), ("75", "75 %"), ("50", "50 %"), ("33", "33 %")],
        initial="100",
    )


WORKSHOP_BLOCK_VARIANT_CHOICES = [
    ("inherit", "Hériter du réglage global"),
    ("card", "Carte empilée (image au-dessus)"),
    ("side", "Image à gauche (legacy)"),
    ("side-left", "Image à gauche"),
    ("side-right", "Image à droite"),
    ("compact", "Compact (sans image)"),
    ("timeline", "Timeline"),
]


class WorkshopBlockForm(forms.Form):
    """Édition locale d'un bloc atelier importé (sans toucher au Workshop source)."""

    variant = forms.ChoiceField(
        label="Mise en page",
        choices=WORKSHOP_BLOCK_VARIANT_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "nl-variant-radio"}),
        initial="inherit",
    )
    image_width = forms.IntegerField(
        label="Largeur de l'image",
        min_value=60,
        max_value=280,
        initial=140,
        help_text="px pour variante « image à gauche » — ratio conservé (glisser le bord de l'image dans l'aperçu)",
        widget=forms.NumberInput(
            attrs={
                "type": "range",
                "min": "60",
                "max": "280",
                "step": "10",
                "class": "w-full accent-[#4a6fa5]",
            }
        ),
    )
    title = forms.CharField(label="Titre affiché", max_length=200)
    date_text = forms.CharField(
        label="Dates affichées",
        max_length=150,
        help_text="ex. Samedi 12 septembre, 14h ou Du 1er juillet au 30 septembre",
    )
    location = forms.CharField(label="Lieu affiché", max_length=120, required=False)
    description = forms.CharField(
        label="Description affichée",
        widget=forms.Textarea(attrs=styled({"rows": 6})),
        required=False,
    )
    title_color = forms.CharField(
        label="Couleur du titre", required=False, widget=forms.TextInput(attrs={"type": "color"})
    )
    text_color = forms.CharField(
        label="Couleur du texte", required=False, widget=forms.TextInput(attrs={"type": "color"})
    )
    new_image = forms.ImageField(
        label="Remplacer le visuel (laisser vide pour conserver)",
        required=False,
    )

    def clean_image_width(self):
        v = self.cleaned_data["image_width"]
        # garde-fou : clamp côté serveur, le JS clampe déjà côté client
        return max(60, min(280, int(v)))

    def clean_title_color(self):
        v = self.cleaned_data.get("title_color", "")
        return v.lower() if v else ""

    def clean_text_color(self):
        v = self.cleaned_data.get("text_color", "")
        return v.lower() if v else ""


class SectionForm(forms.ModelForm):
    """Formulaire d'édition d'une section (header médiathèque + fond uniforme)."""

    background_transparent = forms.BooleanField(
        label="Fond transparent",
        required=False,
        help_text="Cochez pour hériter du fond de la newsletter",
    )

    class Meta:
        model = Section
        fields = [
            "title",
            "library_profile",
            "background_color",
            "header_height",
            "header_align",
            "header_overlay",
            "title_align",
            "contact_align",
            "socials_align",
            "show_header_badge",
            "show_header_phone",
            "show_header_address",
            "show_header_website",
            "show_header_facebook",
            "show_header_instagram",
            "show_header_youtube",
            "show_header_tiktok",
            "show_header_x",
            "title_color",
            "text_color",
            "content_title_color",
            "content_text_color",
            "border_style",
            "border_color",
            "border_width",
            "border_radius",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs=styled(
                    {
                        "placeholder": "Laisser vide pour utiliser le nom de la médiathèque"
                    }
                )
            ),
            "background_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "w-full h-9 rounded-lg border border-[#dce3ef] p-0.5 cursor-pointer bg-white",
                }
            ),
            "header_height": forms.Select(attrs={"class": "nl-input"}),
            "header_align": forms.Select(attrs={"class": "nl-input"}),
            "header_overlay": forms.NumberInput(
                attrs={
                    "type": "range",
                    "min": "0.10",
                    "max": "0.70",
                    "step": "0.05",
                    "class": "w-full accent-[#4a6fa5]",
                }
            ),
            "title_align": forms.Select(attrs={"class": "nl-input"}),
            "contact_align": forms.Select(attrs={"class": "nl-input"}),
            "socials_align": forms.Select(attrs={"class": "nl-input"}),
            "show_header_badge": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_phone": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_address": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_website": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_facebook": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_instagram": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_youtube": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_tiktok": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "show_header_x": forms.CheckboxInput(
                attrs={"class": "nl-checkbox"}
            ),
            "title_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "w-full h-9 rounded-lg border border-[#dce3ef] p-0.5 cursor-pointer bg-white",
                }
            ),
            "text_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "w-full h-9 rounded-lg border border-[#dce3ef] p-0.5 cursor-pointer bg-white",
                }
            ),
            "content_title_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "w-full h-9 rounded-lg border border-[#dce3ef] p-0.5 cursor-pointer bg-white",
                }
            ),
            "content_text_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "w-full h-9 rounded-lg border border-[#dce3ef] p-0.5 cursor-pointer bg-white",
                }
            ),
            "border_style": forms.Select(attrs={"class": "nl-input"}),
            "border_color": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "w-full h-9 rounded-lg border border-[#dce3ef] p-0.5 cursor-pointer bg-white",
                }
            ),
            "border_width": forms.NumberInput(
                attrs={
                    "type": "range",
                    "min": "0",
                    "max": "4",
                    "step": "1",
                    "class": "w-full accent-[#4a6fa5]",
                }
            ),
            "border_radius": forms.Select(attrs={"class": "nl-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["title"].help_text = (
            "Laisser vide pour utiliser le nom de la médiathèque"
        )
        self.fields["library_profile"].required = False
        self.fields["library_profile"].empty_label = "— Aucune (section générique) —"
        self.fields["library_profile"].queryset = LibraryProfile.objects.order_by(
            "name"
        )
        self.fields["background_color"].required = False
        self.fields["title_color"].required = False
        self.fields["text_color"].required = False
        self.fields["content_title_color"].required = False
        self.fields["content_text_color"].required = False
        self.fields["border_style"].required = False
        self.fields["border_color"].required = False
        self.fields["border_width"].required = False
        self.fields["border_radius"].required = False
        # transparent initial
        if self.instance and not self.instance.background_color:
            self.fields["background_transparent"].initial = True
        if self.instance and self.instance.title_color:
            self.fields["title_color"].initial = self.instance.title_color
        if self.instance and self.instance.text_color:
            self.fields["text_color"].initial = self.instance.text_color
        if self.instance and self.instance.content_title_color:
            self.fields["content_title_color"].initial = self.instance.content_title_color
        if self.instance and self.instance.content_text_color:
            self.fields["content_text_color"].initial = self.instance.content_text_color

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("background_transparent"):
            cleaned["background_color"] = "transparent"
        else:
            bg = cleaned.get("background_color", "")
            if bg:
                cleaned["background_color"] = bg.lower()
        for f in (
            "title_color",
            "text_color",
            "content_title_color",
            "content_text_color",
            "border_color",
        ):
            v = cleaned.get(f, "")
            if v:
                cleaned[f] = v.lower()
        return cleaned


class EventForm(forms.Form):
    title = forms.CharField(label="Titre de l'événement", max_length=200)
    subtitle = forms.CharField(label="Sous-titre", max_length=200, required=False)
    date_text = forms.CharField(
        label="Dates affichées",
        max_length=150,
        help_text="ex. Du 5 au 19 septembre ou Samedi 12 octobre, 14h",
    )
    body = forms.CharField(
        label="Description", widget=forms.Textarea(attrs=styled({"rows": 6}))
    )
    new_image = forms.ImageField(label="Affiche / visuel", required=False)


class LibraryPickForm(forms.Form):
    """Choix de la médiathèque lors de l'ajout d'un bloc fiche."""

    profile_id = forms.ModelChoiceField(
        label="Médiathèque",
        queryset=LibraryProfile.objects.none(),
        required=False,
        empty_label="— Toutes les fiches —",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile_id"].queryset = LibraryProfile.objects.order_by("name")

    def to_context_dict(self):
        return (
            {"profile_id": self.cleaned_data["profile_id"].pk}
            if (self.cleaned_data.get("profile_id"))
            else {}
        )


class HeaderPresetForm(forms.ModelForm):
    """Formulaire d'un preset d'en-tête médiathèque."""

    class Meta:
        model = HeaderPreset
        fields = [
            "name",
            "header_height",
            "header_align",
            "title_color",
            "text_color",
            "overlay_strength",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "nl-input"}),
            "header_height": forms.Select(attrs={"class": "nl-input"}),
            "header_align": forms.Select(attrs={"class": "nl-input"}),
            "title_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "text_color": forms.TextInput(
                attrs={"type": "color", "class": "nl-color"}
            ),
            "overlay_strength": forms.NumberInput(
                attrs={
                    "type": "range",
                    "min": "0.10",
                    "max": "0.70",
                    "step": "0.05",
                    "class": "w-full accent-[#4a6fa5]",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title_color"].required = False
        self.fields["text_color"].required = False
        self.fields["overlay_strength"].required = False

    def clean_overlay_strength(self):
        v = self.cleaned_data.get("overlay_strength") or "0.35"
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.35
        return str(max(0.10, min(0.70, f)))


BLOCK_TYPE_TO_FORM = {
    "heading": HeadingForm,
    "text": TextForm,
    "button": ButtonForm,
    "spacer": SpacerForm,
    "image": ImageForm,
    "event": EventForm,
    "workshop": WorkshopBlockForm,
}
