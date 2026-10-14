"""Formulaires pour l'application documents."""

from django import forms

from .models import Document, DocumentCategory


class DocumentForm(forms.ModelForm):
    """Formulaire de création/modification d'un document PDF."""

    class Meta:
        model = Document
        fields = [
            "title",
            "description",
            "category",
            "file",
            "display_order",
            "is_published",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].help_text = (
            "PDF uniquement, 10 Mo maximum."
        )
        if self.instance.pk:
            self.fields["file"].required = False
            self.fields["file"].help_text = (
                "PDF uniquement, 10 Mo maximum. Laissez vide pour conserver "
                "le fichier actuel."
            )


class DocumentCategoryForm(forms.ModelForm):
    """Formulaire de création/modification d'une catégorie de documents."""

    class Meta:
        model = DocumentCategory
        fields = ["name", "icon", "description", "display_order"]
