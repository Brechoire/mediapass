"""Tests de l'application documents (page publique, CRUD superadmin, PDF)."""

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Document, DocumentCategory
from .validators import (
    MAX_DOCUMENT_SIZE,
    validate_document_content,
    validate_document_extension,
    validate_document_size,
)


def pdf_file(name="document.pdf"):
    """Retourne un faux PDF minimal dont l'en-tête est valide."""
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class FakeUpload:
    """Objet minimal exposant name/size pour tester les validateurs."""

    def __init__(self, name, size):
        self.name = name
        self.size = size


class MediaTestCase(TestCase):
    """TestCase isolant les fichiers uploadés dans un MEDIA_ROOT temporaire."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()


class ValidatorTests(TestCase):
    def test_extension_non_pdf_rejetee(self):
        with self.assertRaises(ValidationError):
            validate_document_extension(
                SimpleUploadedFile("doc.docx", b"contenu")
            )

    def test_extension_pdf_acceptee(self):
        validate_document_extension(pdf_file())

    def test_contenu_non_pdf_rejete(self):
        with self.assertRaises(ValidationError):
            validate_document_content(
                SimpleUploadedFile("faux.pdf", b"pas un pdf")
            )

    def test_contenu_pdf_accepte(self):
        validate_document_content(pdf_file())

    def test_taille_max_rejetee(self):
        with self.assertRaises(ValidationError):
            validate_document_size(
                FakeUpload("gros.pdf", MAX_DOCUMENT_SIZE + 1)
            )

    def test_taille_ok(self):
        validate_document_size(FakeUpload("ok.pdf", MAX_DOCUMENT_SIZE))


class DocumentCategoryModelTests(TestCase):
    def test_str_et_ordre_par_defaut(self):
        deuxieme = DocumentCategory.objects.create(
            name="Formulaires", display_order=2
        )
        premiere = DocumentCategory.objects.create(
            name="Règlements", display_order=1
        )
        self.assertEqual(str(premiere), "Règlements")
        self.assertEqual(
            list(DocumentCategory.objects.all()), [premiere, deuxieme]
        )


class DocumentModelTests(MediaTestCase):
    def test_str_et_ordre_par_defaut(self):
        category = DocumentCategory.objects.create(name="Règlements")
        second = Document.objects.create(
            title="B", file=pdf_file(), category=category, display_order=1
        )
        first = Document.objects.create(
            title="A", file=pdf_file(), category=category, display_order=0
        )
        self.assertEqual(str(first), "A")
        self.assertEqual(list(category.documents.all()), [first, second])

    def test_nom_de_fichier_randomise(self):
        document = Document.objects.create(title="Doc", file=pdf_file())
        self.assertTrue(document.file.name.startswith("documents/"))
        self.assertTrue(document.file.name.endswith(".pdf"))
        self.assertNotIn("document.pdf", document.file.name)

    def test_validation_modele_rejette_non_pdf(self):
        document = Document(
            title="Faux", file=SimpleUploadedFile("faux.pdf", b"pas un pdf")
        )
        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_file_exists_et_file_size_avec_fichier_manquant(self):
        document = Document.objects.create(title="Doc", file=pdf_file())
        self.assertTrue(document.file_exists)
        self.assertIsNotNone(document.file_size)
        document.file.delete(save=False)
        document.refresh_from_db()
        self.assertFalse(document.file_exists)
        self.assertIsNone(document.file_size)


class DocumentListViewTests(MediaTestCase):
    def setUp(self):
        self.category = DocumentCategory.objects.create(
            name="Règlements", display_order=1
        )
        self.published = Document.objects.create(
            title="Règlement du réseau",
            file=pdf_file(),
            category=self.category,
        )
        self.draft = Document.objects.create(
            title="Brouillon interne",
            file=pdf_file(),
            category=self.category,
            is_published=False,
        )
        self.uncategorized = Document.objects.create(
            title="Marque-page transfert", file=pdf_file()
        )

    def test_acces_anonyme(self):
        response = self.client.get(reverse("documents:document_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Règlement du réseau")
        self.assertContains(response, "Marque-page transfert")
        self.assertContains(response, "Autres documents")

    def test_lien_header_visible_sans_connexion(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'href="/documents/"')

    def test_documents_non_publies_masques(self):
        response = self.client.get(reverse("documents:document_list"))
        self.assertNotContains(response, "Brouillon interne")

    def test_categorie_sans_document_publie_masquee(self):
        vide = DocumentCategory.objects.create(name="Catégorie vide")
        Document.objects.create(
            title="Doc caché",
            file=pdf_file(),
            category=vide,
            is_published=False,
        )
        response = self.client.get(reverse("documents:document_list"))
        self.assertNotContains(response, "Catégorie vide")
        self.assertNotContains(response, "Doc caché")

    def test_page_vide_sans_document(self):
        Document.objects.all().delete()
        response = self.client.get(reverse("documents:document_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucun document disponible")

    def test_bouton_gestion_visible_pour_superuser(self):
        superuser = User.objects.create_superuser("root", password="x")
        self.client.force_login(superuser)
        response = self.client.get(reverse("documents:document_list"))
        self.assertContains(
            response, reverse("documents:document_manage")
        )
        self.assertContains(
            response, f'{reverse("documents:document_manage")}#categories'
        )

    def test_bouton_gestion_masque_pour_utilisateur_simple(self):
        user = User.objects.create_user("simple", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("documents:document_list"))
        self.assertNotContains(
            response, reverse("documents:document_manage")
        )

    def test_fichier_manquant_ne_fait_pas_planter_la_page(self):
        self.published.file.delete(save=False)
        response = self.client.get(reverse("documents:document_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Règlement du réseau")
        self.assertContains(response, "Fichier indisponible")

    def test_boutons_visualiser_et_telecharger(self):
        response = self.client.get(reverse("documents:document_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visualiser")
        self.assertContains(response, "Télécharger")
        self.assertContains(response, 'target="_blank"')
        # Nom de téléchargement propre, dérivé du titre (accents neutralisés)
        self.assertContains(response, 'download="reglement-du-reseau.pdf"')

    def test_recherche_masquee_avec_peu_de_documents(self):
        response = self.client.get(reverse("documents:document_list"))
        self.assertNotContains(response, 'id="searchDocument"')

    def test_recherche_visible_avec_beaucoup_de_documents(self):
        for i in range(5):
            Document.objects.create(
                title=f"Document supplémentaire {i}", file=pdf_file()
            )
        response = self.client.get(reverse("documents:document_list"))
        self.assertContains(response, 'id="searchDocument"')


class DocumentPermissionTests(TestCase):
    def setUp(self):
        self.regular = User.objects.create_user("user", password="x")
        self.staff = User.objects.create_user(
            "staff", password="x", is_staff=True
        )
        self.superuser = User.objects.create_superuser("root", password="x")

    def test_gestion_redirige_anonyme(self):
        response = self.client.get(reverse("documents:document_manage"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/connexion/", response.url)

    def test_gestion_refusee_pour_utilisateur_et_staff(self):
        for user in (self.regular, self.staff):
            self.client.force_login(user)
            response = self.client.get(reverse("documents:document_manage"))
            self.assertEqual(response.status_code, 302)
            self.client.logout()

    def test_gestion_accessible_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("documents:document_manage"))
        self.assertEqual(response.status_code, 200)

    def test_creation_refusee_pour_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("documents:document_create"))
        self.assertEqual(response.status_code, 302)


class DocumentManageViewTests(MediaTestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", password="x")
        self.client.force_login(self.superuser)
        self.category = DocumentCategory.objects.create(name="Règlements")
        self.document = Document.objects.create(
            title="Règlement réseau",
            file=pdf_file(),
            category=self.category,
        )
        self.other = Document.objects.create(
            title="Marque-page", file=pdf_file(), is_published=False
        )

    def test_liste_affiche_tous_les_documents(self):
        response = self.client.get(reverse("documents:document_manage"))
        self.assertContains(response, "Règlement réseau")
        self.assertContains(response, "Marque-page")
        self.assertContains(response, "Brouillon")

    def test_onglets_documents_et_categories(self):
        response = self.client.get(reverse("documents:document_manage"))
        self.assertContains(response, 'id="panel-documents"')
        self.assertContains(response, 'id="panel-categories"')
        self.assertContains(response, 'data-tab="categories"')
        self.assertContains(response, 'role="tablist"')

    def test_filtre_recherche(self):
        response = self.client.get(
            reverse("documents:document_manage"), {"q": "Marque"}
        )
        self.assertContains(response, "Marque-page")
        self.assertNotContains(response, "Règlement réseau")

    def test_filtre_categorie(self):
        response = self.client.get(
            reverse("documents:document_manage"),
            {"category": self.category.pk},
        )
        self.assertContains(response, "Règlement réseau")
        self.assertNotContains(response, "Marque-page")

    def test_filtre_sans_categorie(self):
        response = self.client.get(
            reverse("documents:document_manage"), {"category": "none"}
        )
        self.assertContains(response, "Marque-page")
        self.assertNotContains(response, "Règlement réseau")


class DocumentCrudViewTests(MediaTestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", password="x")
        self.client.force_login(self.superuser)
        self.category = DocumentCategory.objects.create(name="Formulaires")

    def test_creation_document(self):
        response = self.client.post(
            reverse("documents:document_create"),
            {
                "title": "Formulaire d'inscription",
                "description": "À remplir par la structure",
                "category": self.category.pk,
                "display_order": 1,
                "is_published": "on",
                "file": pdf_file(),
            },
        )
        self.assertRedirects(
            response, reverse("documents:document_manage")
        )
        document = Document.objects.get(title="Formulaire d'inscription")
        self.assertTrue(document.is_published)
        self.assertEqual(document.category, self.category)
        self.assertTrue(document.file.name.startswith("documents/"))

    def test_creation_sans_fichier_refusee(self):
        response = self.client.post(
            reverse("documents:document_create"),
            {"title": "Sans fichier", "display_order": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Document.objects.exists())

    def test_message_confirmation_apres_creation(self):
        response = self.client.post(
            reverse("documents:document_create"),
            {
                "title": "Document message",
                "display_order": 0,
                "is_published": "on",
                "file": pdf_file(),
            },
            follow=True,
        )
        self.assertContains(response, "a été ajouté")

    def test_creation_rejette_extension_non_pdf(self):
        response = self.client.post(
            reverse("documents:document_create"),
            {
                "title": "Word",
                "display_order": 0,
                "file": SimpleUploadedFile("doc.docx", b"contenu"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Format de fichier non supporté")
        self.assertFalse(Document.objects.exists())

    def test_creation_rejette_faux_pdf(self):
        response = self.client.post(
            reverse("documents:document_create"),
            {
                "title": "Faux PDF",
                "display_order": 0,
                "file": SimpleUploadedFile("faux.pdf", b"pas un pdf"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fichier PDF invalide")
        self.assertFalse(Document.objects.exists())

    def test_modification_sans_nouveau_fichier_conserve_le_fichier(self):
        document = Document.objects.create(
            title="Doc", file=pdf_file()
        )
        old_name = document.file.name
        response = self.client.post(
            reverse("documents:document_update", args=[document.pk]),
            {
                "title": "Doc modifié",
                "description": "",
                "category": "",
                "display_order": 0,
                "is_published": "on",
            },
        )
        self.assertRedirects(
            response, reverse("documents:document_manage")
        )
        document.refresh_from_db()
        self.assertEqual(document.title, "Doc modifié")
        self.assertEqual(document.file.name, old_name)

    def test_modification_remplace_et_supprime_ancien_fichier(self):
        document = Document.objects.create(title="Doc", file=pdf_file())
        old_name = document.file.name
        storage = document.file.storage
        self.assertTrue(storage.exists(old_name))

        response = self.client.post(
            reverse("documents:document_update", args=[document.pk]),
            {
                "title": "Doc",
                "description": "",
                "category": "",
                "display_order": 0,
                "is_published": "on",
                "file": pdf_file("nouveau.pdf"),
            },
        )
        self.assertRedirects(
            response, reverse("documents:document_manage")
        )
        document.refresh_from_db()
        self.assertNotEqual(document.file.name, old_name)
        self.assertFalse(storage.exists(old_name))

    def test_suppression_supprime_document_et_fichier(self):
        document = Document.objects.create(title="Doc", file=pdf_file())
        file_name = document.file.name
        storage = document.file.storage

        response = self.client.post(
            reverse("documents:document_delete", args=[document.pk])
        )
        self.assertRedirects(
            response, reverse("documents:document_manage")
        )
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())
        self.assertFalse(storage.exists(file_name))

    def test_suppression_get_non_autorisee(self):
        document = Document.objects.create(title="Doc", file=pdf_file())
        response = self.client.get(
            reverse("documents:document_delete", args=[document.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Document.objects.filter(pk=document.pk).exists())


class DocumentCategoryCrudViewTests(MediaTestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", password="x")
        self.client.force_login(self.superuser)

    def test_creation_categorie(self):
        response = self.client.post(
            reverse("documents:documentcategory_create"),
            {
                "name": "Marque-pages",
                "icon": "bx-book",
                "description": "Marque-pages à imprimer",
                "display_order": 3,
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('documents:document_manage')}#categories",
        )
        category = DocumentCategory.objects.get(name="Marque-pages")
        self.assertEqual(category.icon, "bx-book")

    def test_creation_categorie_nom_unique(self):
        DocumentCategory.objects.create(name="Règlements")
        response = self.client.post(
            reverse("documents:documentcategory_create"),
            {
                "name": "Règlements",
                "icon": "bx-folder",
                "display_order": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "existe")
        self.assertEqual(
            DocumentCategory.objects.filter(name="Règlements").count(), 1
        )

    def test_modification_categorie(self):
        category = DocumentCategory.objects.create(name="Règlements")
        response = self.client.post(
            reverse("documents:documentcategory_update", args=[category.pk]),
            {
                "name": "Règlements du réseau",
                "icon": "bx-book",
                "description": "",
                "display_order": 1,
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('documents:document_manage')}#categories",
        )
        category.refresh_from_db()
        self.assertEqual(category.name, "Règlements du réseau")

    def test_suppression_categorie_conserve_les_documents(self):
        category = DocumentCategory.objects.create(name="Règlements")
        document = Document.objects.create(
            title="Règlement", file=pdf_file(), category=category
        )
        response = self.client.post(
            reverse(
                "documents:documentcategory_delete", args=[category.pk]
            )
        )
        self.assertRedirects(
            response,
            f"{reverse('documents:document_manage')}#categories",
        )
        self.assertFalse(
            DocumentCategory.objects.filter(pk=category.pk).exists()
        )
        document.refresh_from_db()
        self.assertIsNone(document.category)
