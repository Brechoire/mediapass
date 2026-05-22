from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import KakemonoForm, KakemonoReservationForm
from .models import Kakemono, KakemonoReservation


# Create your views here.
def kakemono(request):
    """Affiche la page de kakaemono."""
    return render(request, "kakemono/index.html")


def kakemono_list(request):
    """Liste tous les kakémonos disponibles."""
    kakemonos = Kakemono.objects.all().order_by("title")
    paginator = Paginator(kakemonos, 12)  # 12 kakémonos par page
    page = request.GET.get("page")
    kakemonos = paginator.get_page(page)
    return render(
        request, "kakemono/kakemono_list.html", {"kakemonos": kakemonos}
    )


def kakemono_detail(request, pk):
    """Affiche les détails d'un kakémono."""
    kakemono = get_object_or_404(Kakemono, pk=pk)
    return render(
        request, "kakemono/kakemono_detail.html", {"kakemono": kakemono}
    )


@staff_member_required
def kakemono_create(request):
    """Crée un nouveau kakémono."""
    if request.method == "POST":
        form = KakemonoForm(request.POST, request.FILES)
        if form.is_valid():
            kakemono = form.save(commit=False)
            kakemono.is_available = (
                True  # Rendre le kakémono immédiatement disponible
            )
            kakemono.save()
            messages.success(request, "Kakémono créé avec succès.")
            return redirect("kakemono:detail", pk=kakemono.pk)
    else:
        form = KakemonoForm()
    return render(
        request,
        "kakemono/kakemono_form.html",
        {"form": form, "action": "Créer"},
    )


@staff_member_required
def kakemono_update(request, pk):
    """Met à jour un kakémono existant."""
    kakemono = get_object_or_404(Kakemono, pk=pk)
    if request.method == "POST":
        form = KakemonoForm(request.POST, request.FILES, instance=kakemono)
        if form.is_valid():
            kakemono = form.save()
            messages.success(request, "Kakémono mis à jour avec succès.")
            return redirect("kakemono:detail", pk=kakemono.pk)
    else:
        form = KakemonoForm(instance=kakemono)
    return render(
        request,
        "kakemono/kakemono_form.html",
        {"form": form, "action": "Modifier"},
    )


@staff_member_required
def kakemono_delete(request, pk):
    """Supprime un kakémono."""
    kakemono = get_object_or_404(Kakemono, pk=pk)
    if request.method == "POST":
        kakemono.delete()
        messages.success(request, "Kakémono supprimé avec succès.")
        return redirect("kakemono:list")
    return render(
        request,
        "kakemono/kakemono_confirm_delete.html",
        {"kakemono": kakemono},
    )


def reservation_create(request):
    """Crée une nouvelle réservation."""
    initial = {}

    # Pré-remplir le kakémono si spécifié dans l'URL
    kakemono_id = request.GET.get("kakemono")
    if kakemono_id:
        try:
            kakemono = Kakemono.objects.get(pk=kakemono_id)
            initial["kakemonos"] = [kakemono.id]  # On passe l'ID du kakémono
        except Kakemono.DoesNotExist:
            pass

    # Pré-remplir les informations de l'utilisateur connecté
    if request.user.is_authenticated:
        initial.update({
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
        })

    if request.method == "POST":
        form = KakemonoReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)

                    # Vérifier la disponibilité des kakémonos
            kakemonos = form.cleaned_data["kakemonos"]
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]

            unavailable_kakemonos = []
            kakemono_ids = [k.id for k in kakemonos]
            conflicting_ids = set(
                KakemonoReservation.objects.filter(
                    kakemonos__in=kakemono_ids,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                    status="confirmed"
                ).values_list("kakemonos", flat=True).distinct()
            )
            for kakemono in kakemonos:
                if kakemono.id in conflicting_ids:
                    unavailable_kakemonos.append(kakemono.title)

            if unavailable_kakemonos:
                messages.error(
                    request,
                    "Les kakémonos suivants ne sont pas disponibles pour les"
                    " dates sélectionnées :"
                    f" {', '.join(unavailable_kakemonos)}",
                )
                return render(
                    request, "kakemono/reservation_form.html", {"form": form}
                )

            # Associer l'utilisateur si connecté
            if request.user.is_authenticated:
                reservation.user = request.user

            # Confirmer automatiquement la réservation
            reservation.status = "confirmed"

            reservation.save()
            form.save_m2m()  # Sauvegarde des relations many-to-many

            messages.success(
                request, "Votre réservation a été confirmée avec succès."
            )
            return redirect("kakemono:reservation-detail", pk=reservation.pk)
    else:
        form = KakemonoReservationForm(initial=initial)

    context = {"form": form, "initial_kakemono_id": kakemono_id}
    return render(request, "kakemono/reservation_form.html", context)


def reservation_detail(request, pk):
    """Affiche les détails d'une réservation."""
    reservation = get_object_or_404(
        KakemonoReservation.objects.prefetch_related("kakemonos"), pk=pk
    )
    return render(
        request,
        "kakemono/reservation_detail.html",
        {"reservation": reservation},
    )


def reservation_list(request):
    """Liste toutes les réservations."""
    # Récupérer toutes les réservations triées par date de début
    reservations = KakemonoReservation.objects.prefetch_related(
        "kakemonos"
    ).all().order_by("-start_date")

    # Pagination : 10 réservations par page
    paginator = Paginator(reservations, 10)
    page = request.GET.get("page")
    reservations = paginator.get_page(page)

    return render(
        request,
        "kakemono/reservation_list.html",
        {"reservations": reservations, "active_tab": "reservations"},
    )


@login_required
def check_availability(request):
    """Vérifie la disponibilité des kakémonos pour une période donnée."""
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    kakemono_ids = request.GET.getlist("kakemono_ids[]")

    if not all([start_date, end_date, kakemono_ids]):
        return JsonResponse({"error": "Paramètres manquants"}, status=400)

    unavailable = []
    conflicting_ids = set()
    if kakemono_ids:
        conflicting_ids = set(
            KakemonoReservation.objects.filter(
                kakemonos__in=kakemono_ids,
                start_date__lte=end_date,
                end_date__gte=start_date,
                status="confirmed"
            ).values_list("kakemonos", flat=True).distinct()
        )
        for kakemono in Kakemono.objects.filter(id__in=kakemono_ids):
            if kakemono.id in conflicting_ids:
                unavailable.append(
                    {"id": kakemono.id, "title": kakemono.title}
                )

    return JsonResponse({"unavailable": unavailable})


def get_reservations(request):
    """API endpoint pour récupérer les réservations pour le calendrier."""
    kakemono_id = request.GET.get("kakemono_id")
    start = request.GET.get("start")
    end = request.GET.get("end")

    # Filtrer les réservations
    reservations = KakemonoReservation.objects.prefetch_related(
        "kakemonos"
    ).filter(status="confirmed")

    if kakemono_id:
        reservations = reservations.filter(kakemonos__id=kakemono_id)

    if start and end:
        start_date = datetime.strptime(start[:10], "%Y-%m-%d").date()
        end_date = datetime.strptime(end[:10], "%Y-%m-%d").date()
        reservations = reservations.filter(
            Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
        )

    # Formater les réservations pour FullCalendar
    events = []
    for reservation in reservations:
        kakemonos_list = ", ".join(
            [k.title for k in reservation.kakemonos.all()]
        )
        events.append({
            "id": reservation.id,
            "title": (
                f"{kakemonos_list} -"
                f" {reservation.first_name} {reservation.last_name}"
            ),
            "start": reservation.start_date.isoformat(),
            "end": reservation.end_date.isoformat(),
            "url": reverse(
                "kakemono:reservation-detail", args=[reservation.id]
            ),
            "backgroundColor": "#3788d8",
            "borderColor": "#3788d8",
            "textColor": "#ffffff",
        })

    return JsonResponse(events, safe=False)


@staff_member_required
def reservation_update(request, pk):
    """Met à jour une réservation existante."""
    reservation = get_object_or_404(
        KakemonoReservation.objects.prefetch_related("kakemonos"), pk=pk
    )
    if request.method == "POST":
        form = KakemonoReservationForm(request.POST, instance=reservation)
        if form.is_valid():
            reservation = form.save()
            messages.success(request, "Réservation mise à jour avec succès.")
            return redirect("kakemono:reservation-detail", pk=reservation.pk)
    else:
        form = KakemonoReservationForm(instance=reservation)
    return render(
        request,
        "kakemono/reservation_form.html",
        {"form": form, "action": "Modifier"},
    )


@staff_member_required
def reservation_delete(request, pk):
    """Supprime une réservation."""
    reservation = get_object_or_404(
        KakemonoReservation.objects.prefetch_related("kakemonos"), pk=pk
    )
    if request.method == "POST":
        reservation.delete()
        messages.success(request, "Réservation supprimée avec succès.")
        return redirect("kakemono:reservation-list")
    return render(
        request,
        "kakemono/reservation_confirm_delete.html",
        {"reservation": reservation},
    )
