"""Vues pour l'application documents."""

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.utils import is_superuser

from .forms import DocumentCategoryForm, DocumentForm
from .models import Document, DocumentCategory


def _published_documents():
    """QuerySet des documents publiés, dans l'ordre d'affichage."""
    return Document.objects.filter(is_published=True).order_by(
        "display_order", "title"
    )


def _category_manage_url():
    """URL de la page de gestion, onglet Catégories ouvert."""
    return f"{reverse('documents:document_manage')}#categories"


def document_list(request):
    """Affiche la page publique des documents PDF téléchargeables."""
    published_documents = _published_documents()

    categories = (
        DocumentCategory.objects.annotate(
            published_count=Count(
                "documents", filter=Q(documents__is_published=True)
            )
        )
        .filter(published_count__gt=0)
        .prefetch_related(
            Prefetch("documents", queryset=published_documents)
        )
    )

    context = {
        "categories": categories,
        "uncategorized_documents": published_documents.filter(
            category__isnull=True
        ),
        "documents_count": published_documents.count(),
    }
    return render(request, "documents/document_list.html", context)


@user_passes_test(is_superuser)
def document_manage(request):
    """Page de gestion des documents et catégories (superadmin)."""
    documents = Document.objects.select_related("category").order_by(
        "category__display_order", "display_order", "title"
    )

    q = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "")
    if q:
        documents = documents.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )
    if selected_category == "none":
        documents = documents.filter(category__isnull=True)
    elif selected_category.isdigit():
        documents = documents.filter(category_id=int(selected_category))

    context = {
        "documents": documents,
        "categories": DocumentCategory.objects.annotate(
            document_count=Count("documents")
        ),
        "q": q,
        "selected_category": selected_category,
    }
    return render(request, "documents/document_manage.html", context)


@user_passes_test(is_superuser)
def document_create(request):
    """Crée un nouveau document (superadmin)."""
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save()
            messages.success(
                request,
                f"Le document « {document.title} » a été ajouté.",
            )
            return redirect("documents:document_manage")
    else:
        form = DocumentForm()
    return render(request, "documents/document_form.html", {"form": form})


@user_passes_test(is_superuser)
def document_update(request, pk):
    """Met à jour un document existant (superadmin)."""
    document = get_object_or_404(Document, pk=pk)
    old_file_name = document.file.name if document.file else None

    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            document = form.save()
            # Un nouveau fichier remplace l'ancien : on nettoie le stockage.
            if (
                old_file_name
                and document.file
                and document.file.name != old_file_name
            ):
                storage = document.file.storage
                if storage.exists(old_file_name):
                    storage.delete(old_file_name)
            messages.success(
                request,
                f"Le document « {document.title} » a été mis à jour.",
            )
            return redirect("documents:document_manage")
    else:
        form = DocumentForm(instance=document)

    context = {"form": form, "document": document}
    return render(request, "documents/document_form.html", context)


@user_passes_test(is_superuser)
@require_POST
def document_delete(request, pk):
    """Supprime un document et son fichier (superadmin, POST uniquement)."""
    document = get_object_or_404(Document, pk=pk)
    title = document.title
    if document.file:
        document.file.delete(save=False)
    document.delete()
    messages.success(request, f"Le document « {title} » a été supprimé.")
    return redirect("documents:document_manage")


@user_passes_test(is_superuser)
def documentcategory_create(request):
    """Crée une nouvelle catégorie de documents (superadmin)."""
    if request.method == "POST":
        form = DocumentCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(
                request,
                f"La catégorie « {category.name} » a été créée.",
            )
            return redirect(_category_manage_url())
    else:
        form = DocumentCategoryForm()
    return render(
        request, "documents/documentcategory_form.html", {"form": form}
    )


@user_passes_test(is_superuser)
def documentcategory_update(request, pk):
    """Met à jour une catégorie de documents (superadmin)."""
    category = get_object_or_404(DocumentCategory, pk=pk)
    if request.method == "POST":
        form = DocumentCategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(
                request,
                f"La catégorie « {category.name} » a été mise à jour.",
            )
            return redirect(_category_manage_url())
    else:
        form = DocumentCategoryForm(instance=category)
    return render(
        request, "documents/documentcategory_form.html", {"form": form}
    )


@user_passes_test(is_superuser)
@require_POST
def documentcategory_delete(request, pk):
    """Supprime une catégorie, sans toucher aux documents liés (superadmin)."""
    category = get_object_or_404(DocumentCategory, pk=pk)
    name = category.name
    category.delete()
    messages.success(
        request,
        f"La catégorie « {name} » a été supprimée. Les documents liés sont "
        "conservés dans « Autres documents ».",
    )
    return redirect(_category_manage_url())
