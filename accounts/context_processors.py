"""Context processors pour l'application accounts."""

from django.contrib.auth.models import User

from .models import LibraryProfile


def library_profiles_context(request):
    """Liste des médiathèques (comptes du groupe « mediatheque ») pour la navigation superuser."""
    if request.user.is_superuser:
        profiles = {
            p.user_id: p
            for p in LibraryProfile.objects.select_related("user").all()
        }
        items = []
        for user in (
            User.objects.filter(groups__name="mediatheque")
            .exclude(username="testmediatheque")
            .order_by("username")
        ):
            profile = profiles.get(user.pk)
            items.append(
                {
                    "pk": user.pk,
                    "name": profile.name if profile and profile.name else user.username,
                }
            )
        return {"library_profiles": items}
    return {"library_profiles": []}
