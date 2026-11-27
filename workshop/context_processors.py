from django.db.models import Q


def pending_posters_count(request):
    """Expose le nombre de demandes d'affiches en attente (visuel manquant).

    Même définition que la liste « demandes » de ``workshops_with_poster`` :
    ateliers avec ``poster_required=True`` et sans image déposée
    (``NULL`` ou chaîne vide, Django enregistrant ``""`` quand aucun
    fichier n'est fourni).

    Retourne 0 pour les anonymes et les utilisateurs qui ne peuvent pas
    voir le lien « Affiches » (hors groupe communication / superuser),
    afin d'éviter une requête inutile.
    """
    if not request.user.is_authenticated:
        return {"pending_posters_count": 0}
    user = request.user
    if not user.is_superuser:
        if not user.groups.filter(name="communication").exists():
            return {"pending_posters_count": 0}
    from .models import Workshop

    count = (
        Workshop.objects.filter(poster_required=True)
        .filter(Q(image__isnull=True) | Q(image=""))
        .count()
    )
    return {"pending_posters_count": count}
