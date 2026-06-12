"""Module de vues pour l'application accounts."""
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .forms import LoginForm


class CustomLoginView(LoginView):
    """Vue de connexion avec option 'Rester connecté'."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm

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
