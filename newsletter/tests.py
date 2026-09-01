"""Tests de l'application newsletter (builder, exports, Sender.net)."""

import datetime
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from library_workshops.models import Workshop as LibraryWorkshop, WorkshopParticipant
from PIL import Image as PILImage

from accounts.models import LibraryProfile

from .models import Block, Newsletter, NewsletterImage
from .services import (
    get_candidate_workshops,
    push_to_sender,
    render_newsletter_email,
    sanitize_html,
)


def tiny_png(name="test.png"):
    buffer = BytesIO()
    PILImage.new("RGB", (4, 4), color=(74, 111, 165)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class BaseNewsletterTestCase(TestCase):
    def setUp(self):
        self.comm_user = User.objects.create_user(
            "comm", password="x", first_name="Co", last_name="Mm"
        )
        self.med_user = User.objects.create_user(
            "med1", password="x", first_name="Medi", last_name="Atheque"
        )
        self.other_med = User.objects.create_user("med2", password="x")
        Group.objects.get_or_create(name="communication")[0].user_set.add(
            self.comm_user
        )
        med_group = Group.objects.get_or_create(name="mediatheque")[0]
        med_group.user_set.add(self.med_user)
        med_group.user_set.add(self.other_med)

        self.profile = LibraryProfile.objects.create(
            user=self.med_user,
            name="Médiathèque d'Anor",
            opening_hours="Lundi : 14h - 18h",
        )

        self.client = Client()

    def make_workshop(
        self, user=None, newsletter=True, start_date=None, status="active", **kw
    ):
        defaults = dict(
            title="Atelier lecture",
            description="Une belle séance.",
            start_date=start_date or datetime.date(2030, 9, 5),
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            created_by=user or self.med_user,
            newsletter=newsletter,
            status=status,
        )
        defaults.update(kw)
        return LibraryWorkshop.objects.create(**defaults)

    def make_newsletter(
        self, period=(datetime.date(2030, 9, 1), datetime.date(2030, 9, 30))
    ):
        return Newsletter.objects.create(
            title="Édition de septembre",
            subject="Les ateliers de septembre",
            preheader="Au programme…",
            period_start=period[0],
            period_end=period[1],
            created_by=self.comm_user,
        )


class AccessTests(BaseNewsletterTestCase):
    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("newsletter:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/connexion/", response.url)

    def test_dashboard_forbidden_for_mediatheque(self):
        self.client.force_login(self.med_user)
        response = self.client.get(reverse("newsletter:index"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_allowed_for_communication(self):
        self.client.force_login(self.comm_user)
        response = self.client.get(reverse("newsletter:index"))
        self.assertEqual(response.status_code, 200)

    def test_builder_allowed_for_superuser(self):
        admin = User.objects.create_superuser("admin", "a@a.fr", "x")
        newsletter = self.make_newsletter()
        self.client.force_login(admin)
        response = self.client.get(reverse("newsletter:builder", args=[newsletter.pk]))
        self.assertEqual(response.status_code, 200)


class CandidateWorkshopsTests(BaseNewsletterTestCase):
    def test_only_newsletter_workshops_in_period(self):
        in_period = self.make_workshop(title="Atelier dans la période")
        out_period = self.make_workshop(
            title="Atelier hors période", start_date=datetime.date(2030, 10, 15)
        )
        unflagged = self.make_workshop(title="Atelier non coché", newsletter=False)
        cancelled = self.make_workshop(title="Atelier annulé", status="cancelled")

        groups = get_candidate_workshops(
            datetime.date(2030, 9, 1), datetime.date(2030, 9, 30)
        )
        titles = [w["workshop"].title for g in groups for w in g["workshops"]]
        self.assertIn(in_period.title, titles)
        self.assertNotIn(out_period.title, titles)
        self.assertNotIn(unflagged.title, titles)
        self.assertNotIn(cancelled.title, titles)

    def test_groups_by_library_profile(self):
        other_profile = LibraryProfile.objects.create(
            user=self.other_med, name="Médiathèque B"
        )
        self.make_workshop()
        self.make_workshop(user=self.other_med, title="Atelier jeux")
        groups = get_candidate_workshops(
            datetime.date(2030, 9, 1), datetime.date(2030, 9, 30)
        )
        names = [g["profile"].name for g in groups]
        self.assertIn("Médiathèque d'Anor", names)
        self.assertIn("Médiathèque B", names)


class BlockOperationTests(BaseNewsletterTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.comm_user)
        self.newsletter = self.make_newsletter()

    def add_block(self, data):
        return self.client.post(
            reverse("newsletter:add_block", args=[self.newsletter.pk]), data
        )

    def test_add_heading_then_text_positions(self):
        self.add_block({"block_type": "heading"})
        self.add_block({"block_type": "text"})
        positions = list(self.newsletter.blocks.values_list("position", flat=True))
        self.assertEqual(positions, [0, 1])
        types = list(self.newsletter.blocks.values_list("block_type", flat=True))
        self.assertEqual(types, ["heading", "text"])

    def test_add_block_response_keeps_canvas_anchor(self):
        """La réponse HTMX réinstalle le wrapper #nl-canvas (sinon targetError)."""
        response = self.add_block({"block_type": "heading"})
        content = response.content.decode()
        self.assertIn('id="nl-canvas"', content)
        self.assertTrue(content.lstrip().startswith("<div"))

    def test_style_only_update_on_separator(self):
        block = Block.objects.create(
            newsletter=self.newsletter, position=0, block_type="separator"
        )
        self.client.post(
            reverse("newsletter:update_block", args=[self.newsletter.pk, block.pk]),
            {"style_bg_color": "#ffeedd"},
        )
        block.refresh_from_db()
        self.assertEqual(block.style["bg_color"], "#ffeedd")
        self.assertEqual(block.content, {})

    def test_invalid_type_rejected(self):
        self.add_block({"block_type": "hacky"})
        self.assertEqual(self.newsletter.blocks.count(), 0)

    def test_move_up_and_down(self):
        self.add_block({"block_type": "heading"})
        self.add_block({"block_type": "text"})
        heading, text = self.newsletter.blocks.all()

        text.move("up")
        self.assertEqual(list(self.newsletter.blocks.all()), [text, heading])

        text.move("up")  # déjà en premier → no-op
        self.assertEqual(list(self.newsletter.blocks.all()), [text, heading])

    def test_duplicate_and_delete_reorder(self):
        self.add_block({"block_type": "heading"})
        self.add_block({"block_type": "text"})
        text = self.newsletter.blocks.get(block_type="text")
        copy = text.duplicate()
        self.assertEqual(copy.position, 2)
        self.assertEqual(self.newsletter.blocks.count(), 3)

        copy.delete()
        self.assertEqual(
            list(self.newsletter.blocks.values_list("position", flat=True)), [0, 1]
        )

    def test_cannot_add_same_workshop_twice(self):
        workshop = self.make_workshop()
        url = reverse("newsletter:add_block", args=[self.newsletter.pk])
        self.client.post(url, {"block_type": "workshop", "workshop_id": workshop.pk})
        self.client.post(url, {"block_type": "workshop", "workshop_id": workshop.pk})
        self.assertEqual(
            self.newsletter.blocks.filter(block_type="workshop").count(), 1
        )

    def test_update_text_block_sanitizes_html(self):
        block = Block.objects.create(
            newsletter=self.newsletter,
            position=0,
            block_type="text",
            content={"html": "", "align": "left", "font_size": 15},
        )
        self.client.post(
            reverse("newsletter:update_block", args=[self.newsletter.pk, block.pk]),
            {
                "html": "<p>Bonjour <script>alert(1)</script><strong>monde</strong></p>"
                '<a href="javascript:evil()">lien</a>',
                "align": "left",
                "font_size": 16,
                "style_bg_color": "#ffffff",
                "style_padding": "16px 24px",
            },
        )
        block.refresh_from_db()
        self.assertNotIn("<script>", block.content["html"])
        self.assertIn("<strong>monde</strong>", block.content["html"])
        self.assertNotIn("href", block.content["html"])
        self.assertEqual(block.style["bg_color"], "#ffffff")
        self.assertEqual(block.style["padding"], "16px 24px")

    def test_update_heading_with_style(self):
        block = Block.objects.create(
            newsletter=self.newsletter,
            position=0,
            block_type="heading",
            content={"text": "Titre", "align": "left", "size": 28, "color": "#1e293b"},
        )
        self.client.post(
            reverse("newsletter:update_block", args=[self.newsletter.pk, block.pk]),
            {
                "text": "Nouveau titre",
                "align": "center",
                "size": 32,
                "color": "#123456",
            },
        )
        block.refresh_from_db()
        self.assertEqual(block.content["text"], "Nouveau titre")


class SanitizeTests(TestCase):
    def test_sanitize_keeps_whitelist_only(self):
        dirty = '<p style="x">ok</p><em>italique</em><img src=x onerror=alert(1)>'
        clean = sanitize_html(dirty)
        self.assertIn("<em>italique</em>", clean)
        self.assertNotIn("onerror", clean)
        self.assertNotIn("<img", clean)

    def test_sanitize_empty(self):
        self.assertEqual(sanitize_html(""), "")
        self.assertEqual(sanitize_html(None), "")


class RenderAndExportTests(BaseNewsletterTestCase):
    def test_render_email_contains_content(self):
        newsletter = self.make_newsletter()
        Block.objects.create(
            newsletter=newsletter,
            position=0,
            block_type="heading",
            content={
                "text": "Septembre arrive",
                "align": "left",
                "size": 28,
                "color": "#000",
            },
        )
        html = render_newsletter_email(newsletter)
        self.assertIn("Les ateliers de septembre", html)  # sujet dans <title>
        self.assertIn("Au programme…", html)  # préheader caché
        self.assertIn("Septembre arrive", html)
        self.assertIn('width="600"', html.replace("'", '"'))

    @override_settings(SITE_URL="https://mediapass.test")
    def test_render_email_absolute_image_url(self):
        image = NewsletterImage.objects.create(image=tiny_png(), alt="affiche")
        newsletter = self.make_newsletter()
        Block.objects.create(
            newsletter=newsletter,
            position=0,
            block_type="image",
            content={"image_id": image.pk, "width": "100"},
        )
        html = render_newsletter_email(newsletter)
        self.assertIn("https://mediapass.test" + image.image.url, html)

    def test_empty_image_block_placeholder_canvas_only(self):
        """Bloc image vide : placeholder visible dans le builder, absent de l'email."""
        newsletter = self.make_newsletter()
        Block.objects.create(
            newsletter=newsletter, position=0, block_type="image", content={}
        )
        html = render_newsletter_email(newsletter)
        self.assertNotIn("Aucune image", html)

        self.client.force_login(self.comm_user)
        response = self.client.post(
            reverse("newsletter:add_block", args=[newsletter.pk]),
            {"block_type": "image"},
        )
        self.assertIn("Aucune image", response.content.decode())

    def test_download_attachment(self):
        newsletter = self.make_newsletter()
        self.client.force_login(self.comm_user)
        response = self.client.get(reverse("newsletter:download", args=[newsletter.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"<!DOCTYPE html>"))

    def test_contacts_csv_deduplicated(self):
        newsletter = self.make_newsletter()
        workshop = self.make_workshop()
        WorkshopParticipant.objects.create(
            workshop=workshop,
            first_name="Marie",
            last_name="Dupont",
            email="marie@ex.fr",
            age=34,
            status="confirmed",
        )
        WorkshopParticipant.objects.create(
            workshop=workshop,
            first_name="Paul",
            last_name="Martin",
            email="MARIE@EX.fr",  # doublon insensible à la casse
            age=41,
            status="confirmed",
        )
        WorkshopParticipant.objects.create(
            workshop=workshop,
            first_name="Zoé",
            last_name="Bernard",
            email="zoe@ex.fr",
            age=29,
            status="waiting",
        )
        WorkshopParticipant.objects.create(
            workshop=workshop,
            first_name="Sans",
            last_name="Email",
            age=52,
            status="confirmed",
        )

        self.client.force_login(self.comm_user)
        response = self.client.get(
            reverse("newsletter:contacts_csv", args=[newsletter.pk])
        )
        if hasattr(response, "streaming_content"):
            body = b"".join(response.streaming_content).decode("utf-8-sig")
        else:
            body = response.content.decode("utf-8-sig")
        lines = body.strip().splitlines()
        self.assertEqual(lines[0], "Nom;Prénom;Email")
        self.assertEqual(
            len(lines), 2
        )  # entête + Marie uniquement (doublons/attente/sans email exclus)
        self.assertIn("Dupont;Marie;marie@ex.fr", lines[1])


class SenderTests(BaseNewsletterTestCase):
    def setUp(self):
        super().setUp()
        self.newsletter = self.make_newsletter()

    @override_settings(SENDER_API_KEY="key-123", SENDER_GROUP_ID="grp01")
    @patch("newsletter.services.requests.post")
    def test_push_success_stores_campaign_id(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": {"id": "e1VMRZ"}}

        success, message = push_to_sender(self.newsletter)

        self.assertTrue(success)
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.sender_campaign_id, "e1VMRZ")
        self.assertEqual(self.newsletter.status, Newsletter.Status.SENT)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["content_type"], "html")
        self.assertEqual(payload["subject"], self.newsletter.subject)
        self.assertEqual(payload["groups"], ["grp01"])

    @override_settings(SENDER_API_KEY="")
    def test_push_without_api_key_fails_gracefully(self):
        success, message = push_to_sender(self.newsletter)
        self.assertFalse(success)
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.status, Newsletter.Status.DRAFT)

    @override_settings(SENDER_API_KEY="key-123")
    @patch("newsletter.services.requests.post")
    def test_push_http_error_returns_message(self, mock_post):
        mock_post.return_value.status_code = 422
        mock_post.return_value.text = '{"message":"bad"}'
        success, message = push_to_sender(self.newsletter)
        self.assertFalse(success)
        self.assertIn("422", message)


class FicheTests(BaseNewsletterTestCase):
    def test_ma_fiche_requires_mediatheque_group(self):
        self.client.force_login(self.comm_user)
        response = self.client.get(reverse("newsletter:ma_fiche"))
        self.assertEqual(response.status_code, 302)

    def test_mediatheque_creates_own_fiche(self):
        self.client.force_login(self.other_med)
        response = self.client.post(
            reverse("newsletter:ma_fiche"),
            {"name": "Médiathèque B", "opening_hours": "Mardi : 10h - 17h"},
        )
        self.assertEqual(response.status_code, 302)
        profile = LibraryProfile.objects.get(user=self.other_med)
        self.assertEqual(profile.name, "Médiathèque B")
        self.assertIn("Mardi : 10h - 17h", profile.hours_lines)

    def test_owner_can_edit_but_other_mediatheque_cannot(self):
        self.client.force_login(self.other_med)
        response = self.client.get(
            reverse("newsletter:fiche_edit", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 302)  # pas sa fiche

        self.client.force_login(self.med_user)
        response = self.client.get(
            reverse("newsletter:fiche_edit", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_communication_can_edit_any_fiche_and_list_them(self):
        self.client.force_login(self.comm_user)
        self.assertEqual(
            self.client.get(reverse("newsletter:fiche_list")).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse("newsletter:fiche_edit", args=[self.profile.pk])
            ).status_code,
            200,
        )


class LegacyPageTests(BaseNewsletterTestCase):
    def test_old_newsletter_url_redirects_to_builder_app(self):
        admin = User.objects.create_superuser("admin2", "a@a.fr", "x")
        self.client.force_login(admin)
        response = self.client.get("/mediatheque/ateliers/newsletter/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("newsletter:index"))


class SettingsTests(BaseNewsletterTestCase):
    def test_settings_update_theme_and_period(self):
        newsletter = self.make_newsletter()
        self.client.force_login(self.comm_user)
        response = self.client.post(
            reverse("newsletter:settings_update", args=[newsletter.pk]),
            {
                "title": "Nouveau titre interne",
                "subject": "Objet modifié",
                "preheader": "aperçu",
                "period_start": "2030-10-01",
                "period_end": "2030-10-31",
                "primary_color": "#ff0000",
                "background_color": "#ffffff",
                "font_family": "Georgia, 'Times New Roman', serif",
                "workshop_default_variant": "side-left",
            },
        )
        self.assertEqual(response.status_code, 200)
        newsletter.refresh_from_db()
        self.assertEqual(newsletter.subject, "Objet modifié")
        self.assertEqual(newsletter.primary_color, "#ff0000")
        self.assertEqual(str(newsletter.period_start), "2030-10-01")

    def test_newsletter_duplicate_resets_state(self):
        newsletter = self.make_newsletter()
        newsletter.sender_campaign_id = "abc"
        newsletter.status = Newsletter.Status.SENT
        newsletter.save()
        Block.objects.create(
            newsletter=newsletter,
            position=0,
            block_type="spacer",
            content={"height": 20},
        )
        copy = newsletter.duplicate()
        self.assertEqual(copy.title, "Édition de septembre (copie)")
        self.assertEqual(copy.status, Newsletter.Status.DRAFT)
        self.assertEqual(copy.sender_campaign_id, "")
        self.assertEqual(copy.blocks.count(), 1)


class ReorderStrictTests(BaseNewsletterTestCase):
    """Garde-fous NL-03 : reorder stricte 400 si ordre partiel/doublon/extra."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.comm_user)
        self.newsletter = self.make_newsletter()

    def test_reorder_sections_partial_returns_400(self):
        from newsletter.models import Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        sec2 = Section.objects.create(newsletter=self.newsletter, position=1, title="B")
        url = reverse("newsletter:reorder_sections", args=[self.newsletter.pk])
        # partiel — manque sec2
        response = self.client.post(url, data='{"order": [%d]}' % sec1.pk, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        sec1.refresh_from_db(); sec2.refresh_from_db()
        self.assertEqual(sec1.position, 0)
        self.assertEqual(sec2.position, 1)

    def test_reorder_sections_duplicate_returns_400(self):
        from newsletter.models import Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        Section.objects.create(newsletter=self.newsletter, position=1, title="B")
        url = reverse("newsletter:reorder_sections", args=[self.newsletter.pk])
        response = self.client.post(url, data='{"order": [%d, %d]}' % (sec1.pk, sec1.pk), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_reorder_sections_extra_unknown_returns_400(self):
        from newsletter.models import Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        sec2 = Section.objects.create(newsletter=self.newsletter, position=1, title="B")
        url = reverse("newsletter:reorder_sections", args=[self.newsletter.pk])
        response = self.client.post(url, data='{"order": [%d, %d, 9999]}' % (sec1.pk, sec2.pk), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_reorder_sections_valid_reorders(self):
        from newsletter.models import Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        sec2 = Section.objects.create(newsletter=self.newsletter, position=1, title="B")
        url = reverse("newsletter:reorder_sections", args=[self.newsletter.pk])
        response = self.client.post(url, data='{"order": [%d, %d]}' % (sec2.pk, sec1.pk), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        sec1.refresh_from_db(); sec2.refresh_from_db()
        self.assertEqual(sec1.position, 1)
        self.assertEqual(sec2.position, 0)

    def test_reorder_blocks_partial_missing_returns_400(self):
        from newsletter.models import Block, Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        b1 = Block.objects.create(newsletter=self.newsletter, section=sec1, position=0, block_type="heading", content={"text": "t1"})
        b2 = Block.objects.create(newsletter=self.newsletter, section=sec1, position=1, block_type="text", content={"html": "h"})
        b3 = Block.objects.create(newsletter=self.newsletter, section=None, position=0, block_type="spacer", content={})
        url = reverse("newsletter:reorder_blocks", args=[self.newsletter.pk])
        import json

        # manque b3
        payload = json.dumps({"blocks": {str(sec1.pk): [b1.pk, b2.pk]}})
        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_reorder_blocks_duplicate_returns_400(self):
        from newsletter.models import Block, Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        b1 = Block.objects.create(newsletter=self.newsletter, section=sec1, position=0, block_type="heading", content={})
        Block.objects.create(newsletter=self.newsletter, section=sec1, position=1, block_type="text", content={})
        url = reverse("newsletter:reorder_blocks", args=[self.newsletter.pk])
        import json

        # doublon b1
        payload = json.dumps({"blocks": {str(sec1.pk): [b1.pk, b1.pk]}})
        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_reorder_blocks_valid_inter_section(self):
        from newsletter.models import Block, Section

        sec1 = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        sec2 = Section.objects.create(newsletter=self.newsletter, position=1, title="B")
        b1 = Block.objects.create(newsletter=self.newsletter, section=sec1, position=0, block_type="heading", content={"text": "t", "align": "left", "size": 28, "color": "#000"})
        b2 = Block.objects.create(newsletter=self.newsletter, section=sec1, position=1, block_type="text", content={"html": "<p>x</p>", "align": "left", "font_size": 15})
        url = reverse("newsletter:reorder_blocks", args=[self.newsletter.pk])
        import json

        payload = json.dumps({"blocks": {str(sec1.pk): [b1.pk], str(sec2.pk): [b2.pk]}})
        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        b1.refresh_from_db(); b2.refresh_from_db()
        self.assertEqual(b1.section_id, sec1.pk)
        self.assertEqual(b2.section_id, sec2.pk)
        self.assertEqual(b1.position, 0)
        self.assertEqual(b2.position, 0)


class ColorValidationTests(BaseNewsletterTestCase):
    """Garde-fous NL-05 : couleurs hex et style injectés rejetés."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.comm_user)
        self.newsletter = self.make_newsletter()

    def test_settings_form_rejects_invalid_hex(self):
        from newsletter.forms import SettingsForm

        form = SettingsForm(
            data={
                "title": "t",
                "subject": "s",
                "period_start": "2030-10-01",
                "period_end": "2030-10-31",
                "primary_color": "#zzzzzz",
                "background_color": "#ffffff",
                "font_family": "Arial, Helvetica, sans-serif",
                "workshop_default_variant": "card",
            },
            instance=self.newsletter,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("primary_color", form.errors)

    def test_section_form_clamps_header_overlay(self):
        from newsletter.forms import SectionForm
        from newsletter.models import Section

        sec = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        form = SectionForm(data={"title": "A", "header_overlay": "99", "header_height": "default", "header_align": "left"}, instance=sec)
        # header_overlay clamp 0.70 — clean renvoie "0.7" (float → str)
        if form.is_valid():
            self.assertEqual(form.cleaned_data["header_overlay"], "0.7")
        else:
            form2 = SectionForm(instance=sec)
            form2.cleaned_data = {"header_overlay": "0.01"}
            self.assertEqual(form2.clean_header_overlay(), "0.1")

    def test_section_form_rejects_invalid_title_color(self):
        from newsletter.forms import SectionForm
        from newsletter.models import Section

        sec = Section.objects.create(newsletter=self.newsletter, position=0, title="A")
        form = SectionForm(data={"title": "A", "title_color": "red", "header_height": "default", "header_align": "left"}, instance=sec)
        self.assertFalse(form.is_valid())
        self.assertIn("title_color", form.errors)

    def test_update_block_rejects_injected_style(self):
        block = Block.objects.create(
            newsletter=self.newsletter, position=0, block_type="separator", content={}
        )
        self.client.post(
            reverse("newsletter:update_block", args=[self.newsletter.pk, block.pk]),
            {
                "style_bg_color": "red; background:url(javascript:alert(1))",
                "style_padding": "16px; position:absolute",
                "style_border_style": "evil",
                "style_border_width": "999",
            },
        )
        block.refresh_from_db()
        # injection doit être ignorée
        self.assertNotIn("red;", block.style.get("bg_color", ""))
        self.assertNotIn("position", block.style.get("padding", ""))
        self.assertNotEqual(block.style.get("border_style"), "evil")
        # border_width clamp 0-4 → 4
        if "border_width" in block.style:
            self.assertEqual(block.style["border_width"], "4")

    def test_update_block_accepts_valid_hex_and_padding(self):
        block = Block.objects.create(
            newsletter=self.newsletter, position=0, block_type="separator", content={}
        )
        self.client.post(
            reverse("newsletter:update_block", args=[self.newsletter.pk, block.pk]),
            {"style_bg_color": "#aabbcc", "style_padding": "8px 16px", "style_border_style": "solid"},
        )
        block.refresh_from_db()
        self.assertEqual(block.style.get("bg_color"), "#aabbcc")
        self.assertEqual(block.style.get("padding"), "8px 16px")
        self.assertEqual(block.style.get("border_style"), "solid")


class PushIdempotenceTests(BaseNewsletterTestCase):
    """Garde-fous NL-07 : push Sender.net idempotent, pas de '-' si sans ID."""

    def setUp(self):
        super().setUp()
        self.newsletter = self.make_newsletter()

    @override_settings(SENDER_API_KEY="key-123")
    @patch("newsletter.services.requests.post")
    def test_second_push_is_idempotent(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": {"id": "camp123"}}
        mock_post.return_value.text = '{"data":{"id":"camp123"}}'
        success1, _ = push_to_sender(self.newsletter)
        self.assertTrue(success1)
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.sender_campaign_id, "camp123")
        self.assertEqual(self.newsletter.status, Newsletter.Status.SENT)
        # second push → idempotent sans appel HTTP
        mock_post.reset_mock()
        success2, msg2 = push_to_sender(self.newsletter)
        self.assertFalse(success2)
        self.assertIn("déjà", msg2.lower())
        mock_post.assert_not_called()
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.sender_campaign_id, "camp123")

    @override_settings(SENDER_API_KEY="key-123")
    @patch("newsletter.services.requests.post")
    def test_push_without_id_does_not_mark_sent(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": {}}
        mock_post.return_value.text = '{"data":{}}'
        success, msg = push_to_sender(self.newsletter)
        self.assertFalse(success)
        self.assertIn("identifiant", msg)
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.status, Newsletter.Status.DRAFT)
        self.assertEqual(self.newsletter.sender_campaign_id, "")

    @override_settings(SENDER_API_KEY="key-123", SENDER_GROUP_ID="grp01")
    @patch("newsletter.services.requests.post")
    def test_send_sender_view_blocks_second_push(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": {"id": "v2id"}}
        mock_post.return_value.text = '{"data":{"id":"v2id"}}'
        self.client.force_login(self.comm_user)
        url = reverse("newsletter:send_sender", args=[self.newsletter.pk])
        # first push via vue
        self.client.post(url)
        self.newsletter.refresh_from_db()
        self.assertEqual(self.newsletter.status, Newsletter.Status.SENT)
        # second push via vue → ne crée pas de nouvelle requête Sender
        mock_post.reset_mock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": {"id": "other"}}
        self.client.post(url)
        mock_post.assert_not_called()


class QueryCountTests(BaseNewsletterTestCase):
    """Non-régression N+1 et pagination."""

    def test_builder_query_count_stable(self):
        newsletter = self.make_newsletter()
        # 2 sections + 4 blocs dont 2 avec image
        from newsletter.models import Section

        sec1 = Section.objects.create(newsletter=newsletter, position=0, title="Anor")
        sec2 = Section.objects.create(newsletter=newsletter, position=1, title="Trélon")
        img = NewsletterImage.objects.create(image=tiny_png(), alt="x")
        for sec in (sec1, sec2):
            for i in range(2):
                Block.objects.create(
                    newsletter=newsletter,
                    section=sec,
                    position=i,
                    block_type="image",
                    content={"image_id": img.pk},
                )
        self.client.force_login(self.comm_user)
        from django.core.cache import cache

        cache.clear()
        with self.assertNumQueries(26):
            self.client.get(reverse("newsletter:builder", args=[newsletter.pk]))

    def test_render_email_no_n_plus_1_images(self):
        newsletter = self.make_newsletter()
        img = NewsletterImage.objects.create(image=tiny_png(), alt="x")
        for i in range(5):
            Block.objects.create(
                newsletter=newsletter,
                position=i,
                block_type="image",
                content={"image_id": img.pk},
            )
        with self.assertNumQueries(3):
            html = render_newsletter_email(newsletter)
            self.assertIn("img", html)

    def test_dashboard_pagination(self):
        # Crée 25 newsletters → 2 pages (20 + 5)
        for i in range(25):
            Newsletter.objects.create(
                title=f"NL {i}",
                period_start=datetime.date(2030, 9, 1),
                period_end=datetime.date(2030, 9, 30),
                created_by=self.comm_user,
            )
        self.client.force_login(self.comm_user)
        resp = self.client.get(reverse("newsletter:index"))
        self.assertEqual(resp.status_code, 200)
        # Pagination : 20 sur page 1
        self.assertContains(resp, "Page 1 sur")
        resp2 = self.client.get(reverse("newsletter:index") + "?page=2")
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "Page 2 sur")
