"""Module de vues pour l'application accounts."""
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from distribution.views import is_distribution_agent, is_distribution_manager

from .forms import LoginForm
from .models import LibraryProfile


class CustomLoginView(LoginView):
    """Vue de connexion avec option 'Rester connecté'."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm

    def get_success_url(self):
        user = self.request.user
        if is_distribution_agent(user) and not is_distribution_manager(user):
            # Comptes terrain : directement vers les campagnes en cours.
            return reverse("distribution:campagne_list")
        return super().get_success_url()

    def form_valid(self, form):
        remember_me = form.cleaned_data.get("remember_me")
        response = super().form_valid(form)
        if not remember_me:
            self.request.session.set_expiry(0)
        else:
            self.request.session.set_expiry(1209600)
        return response


@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return redirect("home")


def mediatheque_public(request, pk):
    """Page publique d'une médiathèque (compte du groupe « mediatheque »)."""
    mediatheque_user = get_object_or_404(User, pk=pk)
    profile = LibraryProfile.objects.filter(user=mediatheque_user).select_related("user").first()
    return render(
        request,
        "accounts/mediatheque_public.html",
        {"profile": profile, "mediatheque_user": mediatheque_user},
    )
