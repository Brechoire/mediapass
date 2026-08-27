"""Modèles de l'application newsletter (builder de campagnes)."""

from django.conf import settings
from django.db import models, transaction

FONT_CHOICES = [
    ("Arial, Helvetica, sans-serif", "Arial"),
    ("'Helvetica Neue', Helvetica, Arial, sans-serif", "Helvetica"),
    ("Verdana, Geneva, sans-serif", "Verdana"),
    ("Tahoma, Verdana, Geneva, sans-serif", "Tahoma"),
    ("'Trebuchet MS', Helvetica, sans-serif", "Trebuchet MS"),
    ("Georgia, 'Times New Roman', serif", "Georgia"),
    ("'Times New Roman', Times, serif", "Times New Roman"),
]

WORKSHOP_VARIANT_CHOICES = [
    ("card", "Carte empilée"),
    ("side", "Image à gauche"),
    ("side-left", "Image à gauche"),
    ("side-right", "Image à droite"),
    ("compact", "Compact (liste)"),
    ("timeline", "Timeline"),
]

BORDER_STYLE_CHOICES = [
    ("none", "Aucune"),
    ("solid", "Pleine"),
    ("dashed", "Pointillée"),
    ("left-accent", "Accent à gauche"),
]

RADIUS_CHOICES = [
    ("0", "Carré (0)"),
    ("6", "Petit 6px"),
    ("8", "Moyen 8px"),
    ("12", "Grand 12px"),
    ("16", "Très grand 16px"),
    ("9999", "Pill"),
]

BLOCK_TYPE_CHOICES = [
    ("heading", "Titre"),
    ("text", "Texte"),
    ("image", "Image"),
    ("button", "Bouton"),
    ("separator", "Séparateur"),
    ("spacer", "Espaceur"),
    ("workshop", "Atelier"),
    ("event", "Événement"),
    ("library", "Médiathèque"),
]


class LibraryProfile(models.Model):
    """Fiche d'une médiathèque : identité et informations pratiques."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_profile",
        verbose_name="Compte médiathèque",
    )
    name = models.CharField("Nom de la médiathèque", max_length=150)
    image = models.ImageField(
        "Image / logo", upload_to="newsletter/libraries/", null=True, blank=True
    )
    description = models.TextField("Description", blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    opening_hours = models.TextField(
        "Horaires d'ouverture",
        blank=True,
        help_text="Une ligne par jour, ex. « Lundi : 14h - 18h »",
    )
    closures = models.TextField(
        "Fermetures exceptionnelles", blank=True, help_text="Une fermeture par ligne"
    )
    website = models.URLField("Site web", max_length=255, blank=True)
    facebook_url = models.URLField("Facebook", max_length=255, blank=True)
    instagram_url = models.URLField("Instagram", max_length=255, blank=True)
    updated_at = models.DateTimeField("Modification", auto_now=True)

    class Meta:
        verbose_name = "Fiche médiathèque"

    def __str__(self):
        return self.name

    @property
    def hours_lines(self):
        return [l.strip() for l in self.opening_hours.splitlines() if l.strip()]

    @property
    def closure_lines(self):
        return [l.strip() for l in self.closures.splitlines() if l.strip()]


class Newsletter(models.Model):
    """Une édition de newsletter construite avec des blocs."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SENT = "sent", "Terminée"

    title = models.CharField("Titre interne", max_length=200)
    subject = models.CharField(
        "Objet de l'email", max_length=200, default="Newsletter Médi@'pass"
    )
    preheader = models.CharField("Texte d'aperçu", max_length=255, blank=True)
    period_start = models.DateField("Début de la période")
    period_end = models.DateField("Fin de la période")
    status = models.CharField(
        "Statut",
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    primary_color = models.CharField(
        "Couleur principale", max_length=7, default="#4a6fa5"
    )
    background_color = models.CharField(
        "Couleur de fond", max_length=7, default="#f4f6fb"
    )
    font_family = models.CharField(
        "Police", max_length=100, choices=FONT_CHOICES, default=FONT_CHOICES[0][0]
    )
    workshop_default_variant = models.CharField(
        "Mise en page par défaut des ateliers",
        max_length=12,
        choices=WORKSHOP_VARIANT_CHOICES,
        default="card",
    )
    workshop_bg_color = models.CharField(
        "Fond par défaut des cartes atelier",
        max_length=20,
        default="#ffffff",
        blank=True,
        help_text="Vide ou 'transparent' = fond de section visible",
    )
    workshop_border_style = models.CharField(
        "Bordure par défaut",
        max_length=12,
        choices=BORDER_STYLE_CHOICES,
        default="solid",
    )
    workshop_border_color = models.CharField(
        "Couleur bordure", max_length=20, default="#e3e9f4", blank=True
    )
    workshop_border_width = models.PositiveIntegerField(  # type: ignore[call-overload]
        verbose_name="Épaisseur bordure (px)", default=1
    )
    workshop_border_radius = models.CharField(
        "Rayon par défaut",
        max_length=4,
        choices=RADIUS_CHOICES,
        default="12",
    )
    workshop_title_color = models.CharField(
        "Couleur titres ateliers", max_length=20, default="", blank=True, help_text="Vide = couleur par défaut de la variante"
    )
    workshop_text_color = models.CharField(
        "Couleur texte ateliers", max_length=20, default="", blank=True, help_text="Vide = couleur par défaut de la variante"
    )
    sender_campaign_id = models.CharField(
        "ID campagne Sender.net", max_length=50, blank=True, editable=False
    )
    sender_pushed_at = models.DateTimeField(
        "Poussée vers Sender.net", null=True, blank=True, editable=False
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="newsletters",
        verbose_name="Créée par",
    )
    created_at = models.DateTimeField("Créée le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifiée le", auto_now=True)

    class Meta:
        verbose_name = "newsletter"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def duplicate(self):
        """Duplique la newsletter, ses sections et ses blocs (retour au statut brouillon)."""
        copy = Newsletter.objects.get(pk=self.pk)
        copy.pk = None
        copy.title = f"{self.title} (copie)"
        copy.status = self.Status.DRAFT
        copy.sender_campaign_id = ""
        copy.sender_pushed_at = None
        copy.save()
        # duplique sections puis blocs (avec mapping ancien -> nouveau)
        section_map = {}
        for sec in self.sections.all():
            old_pk = sec.pk
            sec.pk = None
            sec.newsletter = copy
            sec.save()
            section_map[old_pk] = sec
        for block in self.blocks.all():
            sec = block.section
            block.pk = None
            block.newsletter = copy
            if sec is not None:
                block.section = section_map.get(sec.pk, sec)
                # sec.pk a été changé ci-dessus, donc mapping via old_pk
                # on récupère via old section id stocké avant : utiliser section_map avec old_pk
                # fallback : retrouver par ancienne pk si mapping raté
            block.save()
        # second pass pour corriger les sections des blocs (car sec.pk a changé)
        # plus simple : on a déjà mappé, mais pour les blocs où section était not None,
        # on avait sec = ancienne instance dont pk a été réutilisé ; mapping ok.
        # Pour les blocs hors section, section reste None.
        return copy


class Section(models.Model):
    """Une section regroupant un header médiathèque et ses ateliers. Fond uniforme."""

    newsletter = models.ForeignKey(
        Newsletter, on_delete=models.CASCADE, related_name="sections"
    )
    position = models.PositiveIntegerField("Position", db_index=True)
    library_profile = models.ForeignKey(
        LibraryProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sections",
        verbose_name="Médiathèque",
    )
    title = models.CharField("Titre de section", max_length=200, blank=True)
    background_color = models.CharField(
        "Couleur de fond",
        max_length=20,
        default="#ffffff",
        blank=True,
        help_text="Vide ou 'transparent' = fond de newsletter visible",
    )
    title_color = models.CharField(
        "Couleur titre section", max_length=20, default="", blank=True, help_text="Titre de l'en-tête"
    )
    text_color = models.CharField(
        "Couleur texte section", max_length=20, default="", blank=True, help_text="Texte de l'en-tête"
    )
    content_title_color = models.CharField(
        "Couleur titres du contenu", max_length=20, default="", blank=True, help_text="Titres des ateliers/blocs à l'intérieur"
    )
    content_text_color = models.CharField(
        "Couleur texte du contenu", max_length=20, default="", blank=True, help_text="Texte des blocs à l'intérieur"
    )
    border_style = models.CharField(
        "Bordure",
        max_length=12,
        choices=BORDER_STYLE_CHOICES,
        default="",
        blank=True,
        help_text="Vide = hérite du global",
    )
    border_color = models.CharField(
        "Couleur bordure", max_length=20, default="", blank=True
    )
    border_width = models.PositiveIntegerField(
        verbose_name="Épaisseur bordure (px)", null=True, blank=True
    )  # type: ignore[call-overload]
    border_radius = models.CharField(
        "Rayon",
        max_length=4,
        choices=RADIUS_CHOICES,
        default="",
        blank=True,
        help_text="Vide = hérite du global",
    )

    class Meta:
        verbose_name = "section"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["newsletter", "position"],
                name="unique_section_position_per_newsletter",
            )
        ]

    def __str__(self):
        label = self.title or (
            self.library_profile.name
            if self.library_profile
            else f"Section #{self.position}"
        )
        return f"{label} — {self.newsletter.title}"

    @classmethod
    def next_position(cls, newsletter):
        last = (
            cls.objects.filter(newsletter=newsletter)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
        )
        return 0 if last is None else last + 1

    def move(self, direction):
        delta = {"up": -1, "down": 1}[direction]
        with transaction.atomic():
            # Verrouille les 2 lignes pour éviter race
            neighbor = (
                Section.objects.select_for_update()
                .filter(newsletter=self.newsletter, position=self.position + delta)
                .first()
            )
            if neighbor is None:
                return False
            # Recharge self avec lock
            locked_self = Section.objects.select_for_update().get(pk=self.pk)
            old_pos, old_neighbor = locked_self.position, neighbor.position
            locked_self.position = old_pos + 10**6
            locked_self.save(update_fields=["position"])
            neighbor.position = old_pos
            neighbor.save(update_fields=["position"])
            locked_self.position = old_neighbor
            locked_self.save(update_fields=["position"])
            # Met à jour l'instance courante
            self.position = old_neighbor
        return True

    def delete(self, *args, **kwargs):
        pos = self.position
        super().delete(*args, **kwargs)
        Section.objects.filter(newsletter=self.newsletter, position__gt=pos).update(
            position=models.F("position") - 1
        )


class Block(models.Model):
    """Un bloc de contenu dans une newsletter. Peut appartenir à une section."""

    newsletter = models.ForeignKey(
        Newsletter, on_delete=models.CASCADE, related_name="blocks"
    )
    section = models.ForeignKey(
        "Section",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="blocks",
        verbose_name="Section",
    )
    position = models.PositiveIntegerField("Position", db_index=True)
    block_type = models.CharField("Type", max_length=20, choices=BLOCK_TYPE_CHOICES)
    content = models.JSONField("Contenu", default=dict, blank=True)
    style = models.JSONField("Style", default=dict, blank=True)
    # Dénormalisation pour éviter le scan JSONField sur content__workshop_id (indexé)
    cached_workshop_id = models.PositiveIntegerField(
        null=True, blank=True, db_index=True, verbose_name="Atelier source (cache)"
    )

    class Meta:
        verbose_name = "bloc"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["newsletter", "section", "position"],
                name="unique_block_position_per_section",
            )
        ]
        indexes = [
            models.Index(fields=["newsletter", "block_type", "cached_workshop_id"], name="idx_block_nl_type_ws"),
        ]

    def __str__(self):
        label = dict(BLOCK_TYPE_CHOICES).get(self.block_type, self.block_type)
        return f"{label} #{self.position} — {self.newsletter.title}"

    @property
    def type_label(self):
        return dict(BLOCK_TYPE_CHOICES).get(self.block_type, self.block_type)

    @property
    def partial_name(self):
        return f"newsletter/partials/blocks/{self.block_type}.html"

    @property
    def image_obj(self):
        """NewsletterImage référencée par le bloc, le cas échéant. Supporte prefetch via _cached_image_obj."""
        if hasattr(self, "_cached_image_obj"):
            return self._cached_image_obj
        image_id = (self.content or {}).get("image_id")
        if not image_id:
            return None
        return NewsletterImage.objects.filter(pk=image_id).first()

    def set_cached_image(self, image_obj):
        """Utilisé par le prefetch bulk pour éviter N+1."""
        self._cached_image_obj = image_obj

    @property
    def workshop_variant(self):
        v = (self.content or {}).get("variant") or "inherit"
        if v == "inherit":
            return self.newsletter.workshop_default_variant
        return v

    @property
    def workshop_image_width(self):
        try:
            return int((self.content or {}).get("image_width") or 140)
        except (TypeError, ValueError):
            return 140

    @property
    def section_background_color(self):
        return self.section.background_color if self.section else ""

    @property
    def section_border_style(self):
        return self.section.border_style if self.section else ""

    @property
    def section_border_color(self):
        return self.section.border_color if self.section else ""

    @property
    def section_border_width(self):
        return self.section.border_width if self.section and self.section.border_width is not None else ""

    @property
    def section_border_radius(self):
        return self.section.border_radius if self.section else ""

    @property
    def section_title_color(self):
        return self.section.title_color if self.section else ""

    @property
    def section_text_color(self):
        return self.section.text_color if self.section else ""

    @property
    def section_content_title_color(self):
        return self.section.content_title_color if self.section else ""

    @property
    def section_content_text_color(self):
        return self.section.content_text_color if self.section else ""

    @classmethod
    def next_position(cls, newsletter, section=None):
        qs = cls.objects.filter(newsletter=newsletter, section=section)
        last = qs.order_by("-position").values_list("position", flat=True).first()
        return 0 if last is None else last + 1

    def move(self, direction):
        """Déplace le bloc d'une position en permutant avec son voisin (même section)."""
        delta = {"up": -1, "down": 1}[direction]
        with transaction.atomic():
            neighbor = (
                Block.objects.select_for_update()
                .filter(newsletter=self.newsletter, section=self.section, position=self.position + delta)
                .first()
            )
            if neighbor is None:
                return False
            locked_self = Block.objects.select_for_update().get(pk=self.pk)
            old_pos, old_neighbor_pos = locked_self.position, neighbor.position
            locked_self.position = old_pos + 10**6
            locked_self.save(update_fields=["position"])
            neighbor.position = old_pos
            neighbor.save(update_fields=["position"])
            locked_self.position = old_neighbor_pos
            locked_self.save(update_fields=["position"])
            self.position = old_neighbor_pos
        return True

    def duplicate(self):
        """Insère une copie du bloc juste après lui-même (même section)."""
        Block.objects.filter(
            newsletter=self.newsletter,
            section=self.section,
            position__gt=self.position,
        ).update(position=models.F("position") + 1)
        copy = Block.objects.get(pk=self.pk)
        copy.pk = None
        copy.position = self.position + 1
        copy.save()
        return copy

    def delete(self, *args, **kwargs):
        position = self.position
        newsletter = self.newsletter
        section = self.section
        super().delete(*args, **kwargs)
        Block.objects.filter(
            newsletter=newsletter, section=section, position__gt=position
        ).update(position=models.F("position") - 1)


class NewsletterImage(models.Model):
    """Image téléversée réutilisable dans les blocs."""

    image = models.ImageField("Image", upload_to="newsletter/blocks/")
    alt = models.CharField("Texte alternatif", max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Téléversée par",
    )
    created_at = models.DateTimeField("Ajoutée le", auto_now_add=True)

    class Meta:
        verbose_name = "image newsletter"

    def __str__(self):
        return self.alt or f"Image #{self.pk}"
