from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.utils import is_staff_or_superuser
from ..forms import ApprovalForm, DisapprovalForm, ReservationForm
from ..models import Product, Reservation, Structure


@user_passes_test(is_staff_or_superuser)
def create_reservation(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reservations = Reservation.objects.filter(product=product)
    if request.method == "POST":
        form = ReservationForm(request.POST, product=product)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.product = product

            conflit = Reservation.objects.filter(
                product=product,
                start_date__lte=reservation.end_date,
                end_date__gte=reservation.start_date,
            ).exclude(pk=reservation.pk).exists()

            if conflit:
                messages.error(
                    request, "Ce produit est d\u00e9j\u00e0 r\u00e9serv\u00e9 pour cette p\u00e9riode."
                )
                return redirect("create_reservation", product_id=product.id)

            reservation.save()
            messages.success(request, "R\u00e9servation cr\u00e9\u00e9e avec succ\u00e8s.")
            return redirect("product_detail", product_id=product.id)
    else:
        form = ReservationForm(product=product)
    return render(
        request,
        "shop/create_reservation.html",
        {"product": product, "form": form, "reservations": reservations},
    )


@user_passes_test(is_staff_or_superuser)
def reservation_details(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("product__category", "structure"), pk=pk
    )
    return render(
        request, "shop/reservation_details.html", {"reservation": reservation}
    )


@user_passes_test(is_staff_or_superuser)
def reservation_list(request):
    selected_year = request.GET.get('year', datetime.now().year)
    selected_status = request.GET.get('status', '')
    selected_structure = request.GET.get('structure', '')

    try:
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_year = datetime.now().year

    reservations = Reservation.objects.select_related(
        "product", "structure"
    ).all()

    if selected_year:
        reservations = reservations.filter(
            start_date__year=selected_year
        )

    if selected_status == 'approved':
        reservations = reservations.filter(is_approved=True)
    elif selected_status == 'pending':
        reservations = reservations.filter(
            is_approved=False,
            is_rejected=False,
            disapproval_reason__isnull=True
        )
    elif selected_status == 'rejected':
        reservations = reservations.filter(
            Q(is_rejected=True) | Q(disapproval_reason__isnull=False)
        )

    if selected_structure:
        try:
            structure_id = int(selected_structure)
            reservations = reservations.filter(structure_id=structure_id)
        except (ValueError, TypeError):
            pass

    reservations = reservations.order_by("-start_date")

    paginator = Paginator(reservations, 25)
    page_number = request.GET.get("page", 1)
    reservations = paginator.get_page(page_number)

    current_year = datetime.now().year
    year_stats = Reservation.objects.filter(
        start_date__year=current_year
    ).aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(is_approved=True)),
        pending=Count("id", filter=Q(is_approved=False, is_rejected=False, disapproval_reason__isnull=True)),
        rejected=Count("id", filter=Q(is_rejected=True) | Q(disapproval_reason__isnull=False)),
    )
    total_reservations = year_stats["total"]
    current_year_reservations = year_stats["total"]
    approved_reservations = year_stats["approved"]
    pending_reservations = year_stats["pending"]
    rejected_reservations = year_stats["rejected"]

    available_years = list(Reservation.objects.values_list(
        'start_date__year', flat=True
    ).distinct().order_by('-start_date__year'))

    structures = Structure.objects.filter(
        is_registered=True
    ).order_by('name')

    context = {
        'reservations': reservations,
        'page_obj': reservations,
        'paginator': paginator,
        'total_reservations': total_reservations,
        'approved_reservations': approved_reservations,
        'pending_reservations': pending_reservations,
        'rejected_reservations': rejected_reservations,
        'current_year_reservations': current_year_reservations,
        'available_years': available_years,
        'structures': structures,
        'selected_year': selected_year,
        'selected_status': selected_status,
        'selected_structure': selected_structure,
        'current_year': current_year,
    }

    return render(request, "shop/reservation_list.html", context)


@login_required
@user_passes_test(is_staff_or_superuser)
def reservation_calendar(request):
    today = timezone.now()
    today_date = today.date()
    end_date = today + timedelta(days=15)

    kpi_stats = Reservation.objects.aggregate(
        active=Count("id", filter=Q(
            is_approved=True, start_date__date__lte=today_date,
            end_date__date__gte=today_date
        )),
        departures=Count("id", filter=Q(
            is_approved=True, start_date__date=today_date
        )),
        returns=Count("id", filter=Q(
            is_approved=True, end_date__date=today_date
        )),
        pending=Count("id", filter=Q(
            is_approved=False, is_rejected=False,
            disapproval_reason__isnull=True
        )),
    )
    active_reservations_count = kpi_stats["active"]
    departures_today_count = kpi_stats["departures"]
    returns_today_count = kpi_stats["returns"]
    pending_count = kpi_stats["pending"]

    selected_structure = request.GET.get('structure', '')
    selected_product = request.GET.get('product', '')

    upcoming_reservations = Reservation.objects.filter(
        is_approved=True,
        start_date__gte=today,
        start_date__lte=end_date
    ).select_related('product', 'structure').order_by('start_date')

    upcoming_returns = Reservation.objects.filter(
        is_approved=True,
        end_date__gte=today,
        end_date__lte=end_date
    ).select_related('product', 'structure').order_by('end_date')

    if selected_structure:
        try:
            structure_id = int(selected_structure)
            upcoming_reservations = upcoming_reservations.filter(
                structure_id=structure_id
            )
            upcoming_returns = upcoming_returns.filter(structure_id=structure_id)
        except (ValueError, TypeError):
            pass

    if selected_product:
        try:
            product_id = int(selected_product)
            upcoming_reservations = upcoming_reservations.filter(
                product_id=product_id
            )
            upcoming_returns = upcoming_returns.filter(product_id=product_id)
        except (ValueError, TypeError):
            pass

    structures = Structure.objects.filter(is_registered=True).order_by('name')
    products_data = Product.objects.filter(status=True).order_by('name')

    return render(request, "shop/reservation_calendar.html", {
        'upcoming_reservations': upcoming_reservations,
        'upcoming_returns': upcoming_returns,
        'today': today,
        'active_reservations_count': active_reservations_count,
        'departures_today_count': departures_today_count,
        'returns_today_count': returns_today_count,
        'pending_count': pending_count,
        'structures': structures,
        'products': products_data,
        'selected_structure': selected_structure,
        'selected_product': selected_product,
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def reservation_calendar_events(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    selected_structure = request.GET.get('structure', '')
    selected_product = request.GET.get('product', '')

    reservations = Reservation.objects.filter(is_approved=True)

    if start and end:
        reservations = reservations.filter(
            start_date__lte=end,
            end_date__gte=start
        )

    if selected_structure:
        try:
            reservations = reservations.filter(structure_id=int(selected_structure))
        except (ValueError, TypeError):
            pass

    if selected_product:
        try:
            reservations = reservations.filter(product_id=int(selected_product))
        except (ValueError, TypeError):
            pass

    events = []
    for r in reservations.select_related('product', 'structure'):
        color = r.structure.color if r.structure.color else '#6366f1'
        events.append({
            'id': r.pk,
            'title': f"{r.product.name} - {r.structure.name}",
            'start': r.start_date.strftime('%Y-%m-%dT%H:%M:%S'),
            'end': r.end_date.strftime('%Y-%m-%dT%H:%M:%S'),
            'color': color,
            'extendedProps': {
                'product': r.product.name,
                'structure': r.structure.name,
                'quantity': r.quantity,
            },
            'url': reverse("reservation_details", args=[r.pk]),
        })

    return JsonResponse(events, safe=False)


@user_passes_test(is_staff_or_superuser)
def approve_reservation(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("product", "structure"), pk=pk
    )
    if reservation.is_approved:
        return redirect("reservation_list")
    if request.method == "POST":
        form = ApprovalForm(request.POST)
        if form.is_valid():
            reservation.is_approved = True
            reservation.save()
            from notifications.email_service import send_notification
            send_notification("reservation_approved", {
                "reservation": reservation,
                "product": reservation.product,
            }, extra_recipients=[reservation.structure.email])
            messages.success(
                request,
                "La r\u00e9servation a \u00e9t\u00e9 approuv\u00e9e avec succ\u00e8s.",
            )
            return redirect("reservation_list")
    else:
        form = ApprovalForm()
    return render(
        request,
        "shop/approve_reservation.html",
        {"reservation": reservation, "form": form},
    )


@user_passes_test(is_staff_or_superuser)
def disapprove_reservation(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("product", "structure"), pk=pk
    )

    if request.method == "POST":
        form = DisapprovalForm(request.POST)
        if form.is_valid():
            reservation.reject_reservation(
                reason=form.cleaned_data["reason"],
                comment=form.cleaned_data["comment"]
            )

            from notifications.email_service import send_notification
            send_notification("reservation_disapproved", {
                "reservation": reservation,
                "product": reservation.product,
                "reason": form.cleaned_data["reason"],
                "comment": form.cleaned_data["comment"],
            }, extra_recipients=[reservation.structure.email])

            messages.success(
                request,
                "La r\u00e9servation a \u00e9t\u00e9 d\u00e9sapprouv\u00e9e avec succ\u00e8s et un "
                "email a \u00e9t\u00e9 envoy\u00e9.",
            )
            return redirect("reservation_list")
    else:
        form = DisapprovalForm()

    return render(
        request,
        "shop/disapprove_reservation.html",
        {"reservation": reservation, "form": form},
    )


@user_passes_test(is_staff_or_superuser)
def delete_reservation(request, pk):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])
    get_object_or_404(Reservation, pk=pk).delete()
    messages.success(request, "La r\u00e9servation a \u00e9t\u00e9 supprim\u00e9e avec succ\u00e8s.")
    return redirect("reservation_list")
