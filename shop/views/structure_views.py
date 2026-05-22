from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.utils import is_staff_or_superuser
from ..forms import StructureForm, StructureRegisterForm
from ..models import Product, Reservation, Structure
from workshop.models import Workshop


@user_passes_test(is_staff_or_superuser)
def structure_list(request):
    q = request.GET.get("q", "")
    sort = request.GET.get("sort", "name")
    dir = request.GET.get("dir", "asc")

    sort_map = {"name": "name", "city": "city", "reservations": "reservation_count"}
    sort_field = sort_map.get(sort, "name")
    if dir == "desc":
        sort_field = f"-{sort_field}"

    structures = Structure.objects.annotate(
        reservation_count=Count("reservations")
    )
    if q:
        structures = structures.filter(name__icontains=q)
    structures = structures.order_by(sort_field)

    paginator = Paginator(structures, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "shop/structure_list.html",
        {"structures": page_obj, "page_obj": page_obj, "q": q, "sort": sort, "dir": dir},
    )


@user_passes_test(is_staff_or_superuser)
def structure_list_export(request):
    import csv
    from django.http import HttpResponse

    structures = Structure.objects.all().order_by("name")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="structures.csv"'

    writer = csv.writer(response)
    writer.writerow(["ID", "Nom", "Ville", "Email", "Active", "Inscrite"])
    for s in structures:
        writer.writerow([s.pk, s.name, s.city, s.email, "Oui" if s.valid else "Non", "Oui" if s.is_registered else "Non"])
    return response


@user_passes_test(is_staff_or_superuser)
def structure_detail(request, pk):
    structure = get_object_or_404(Structure, pk=pk)
    current_year = timezone.now().year
    selected_year = int(request.GET.get("year", current_year))
    prev_year = selected_year - 1

    years_all = list(
        Reservation.objects.filter(structure=structure)
        .dates("start_date", "year")
        .values_list("start_date__year", flat=True)
    ) or []
    workshop_years = list(
        Workshop.objects.filter(location__city=structure.city)
        .dates("date", "year")
        .values_list("date__year", flat=True)
    ) or []
    available_years = sorted(set(years_all + workshop_years), reverse=True) or [current_year]

    reservations_qs = Reservation.objects.filter(structure=structure)
    r_year = reservations_qs.filter(start_date__year=selected_year)
    r_prev = reservations_qs.filter(start_date__year=prev_year)

    r_year_stats = r_year.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(is_approved=True)),
        pending=Count("id", filter=Q(is_approved=False, is_rejected=False)),
        rejected=Count("id", filter=Q(is_rejected=True)),
    )
    r_prev_stats = r_prev.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(is_approved=True)),
    )

    total_reservations = reservations_qs.count()
    total_reservations_year = r_year_stats["total"]
    approved_reservations_year = r_year_stats["approved"]
    pending_reservations_year = r_year_stats["pending"]
    rejected_reservations_year = r_year_stats["rejected"]
    prev_reservations_count = r_prev_stats["total"]
    prev_reservations_approved = r_prev_stats["approved"]

    def pct(val, total):
        return round((val / total) * 100, 1) if total > 0 else 0

    approved_pct = pct(approved_reservations_year, total_reservations_year)
    pending_pct = pct(pending_reservations_year, total_reservations_year)
    rejected_pct = pct(rejected_reservations_year, total_reservations_year)

    def variation(curr, prev):
        return round(((curr - prev) / prev) * 100, 1) if prev > 0 else 0

    reservations_variation = variation(total_reservations_year, prev_reservations_count)
    approved_variation = variation(approved_reservations_year, prev_reservations_approved)

    reservations_by_product = (
        r_year.values("product__name", "product__category__name")
        .annotate(
            count=Count("id"),
            approved_count=Count("id", filter=Q(is_approved=True)),
            pending_count=Count("id", filter=Q(is_approved=False, is_rejected=False)),
        )
        .order_by("-count")
    )
    reservations_by_category = (
        r_year.values("product__category__name")
        .annotate(count=Count("id"), approved_count=Count("id", filter=Q(is_approved=True)))
        .order_by("-count")
    )

    monthly_raw = (
        r_year.annotate(month=TruncMonth("start_date"))
        .values("month")
        .annotate(
            count=Count("id"),
            approved=Count("id", filter=Q(is_approved=True)),
            qty=Coalesce(Sum("quantity"), 0),
        )
        .order_by("month")
    )
    monthly_map = {m["month"].month if m["month"] else 0: m for m in monthly_raw}
    monthly_reservations = []
    for m in range(1, 13):
        d = monthly_map.get(m, {})
        monthly_reservations.append(
            {"month": m, "count": d.get("count", 0), "approved": d.get("approved", 0), "quantity": d.get("qty", 0)}
        )

    ws_qs = Workshop.objects.filter(location__city=structure.city)
    ws_year = ws_qs.filter(date__year=selected_year)
    ws_prev = ws_qs.filter(date__year=prev_year)

    ws_year_stats = ws_year.aggregate(
        total=Count("id"),
        classic=Count("id", filter=Q(class_welcome=False)),
        class_welcome=Count("id", filter=Q(class_welcome=True)),
        registered=Coalesce(Sum("number_registered"), 0),
        attendees=Coalesce(Sum("number_attendees"), 0),
    )
    ws_prev_stats = ws_prev.aggregate(
        total=Count("id"),
        registered=Coalesce(Sum("number_registered"), 0),
    )

    total_workshops_year = ws_year_stats["total"]
    total_registered_year = ws_year_stats["registered"]
    total_attendees_year = ws_year_stats["attendees"]
    attendance_rate_year = pct(total_attendees_year, total_registered_year)
    prev_workshops_count = ws_prev_stats["total"]
    prev_workshops_registered = ws_prev_stats["registered"]
    workshops_variation = variation(total_workshops_year, prev_workshops_count)
    registered_variation = variation(total_registered_year, prev_workshops_registered)

    workshops_by_location = (
        ws_year.values("location__name")
        .annotate(
            count=Count("id"),
            total_registered=Coalesce(Sum("number_registered"), 0),
            classic_count=Count("id", filter=Q(class_welcome=False)),
            class_welcome_count=Count("id", filter=Q(class_welcome=True)),
        )
        .order_by("-count")
    )

    ws_monthly_raw = (
        ws_year.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            count=Count("id"),
            registered=Coalesce(Sum("number_registered"), 0),
            attendees=Coalesce(Sum("number_attendees"), 0),
        )
        .order_by("month")
    )
    ws_monthly_map = {m["month"].month if m["month"] else 0: m for m in ws_monthly_raw}
    monthly_workshops = []
    for m in range(1, 13):
        d = ws_monthly_map.get(m, {})
        monthly_workshops.append(
            {"month": m, "count": d.get("count", 0), "registered": d.get("registered", 0), "attendees": d.get("attendees", 0)}
        )

    most_registered_workshops = ws_year.filter(number_registered__gt=0).order_by("-number_registered")[:5]
    best_attendance_workshops = sorted(
        [{"workshop": w, "attendance_rate": pct(w.number_attendees, w.number_registered)}
         for w in ws_year.filter(number_registered__gt=0)],
        key=lambda x: x["attendance_rate"],
        reverse=True,
    )[:5]

    reservations_data = r_year.select_related("product")

    return render(
        request,
        "shop/structure_detail.html",
        {
            "structure": structure,
            "selected_year": selected_year,
            "previous_year": prev_year if prev_year in available_years else None,
            "available_years": available_years,
            "total_reservations": total_reservations,
            "total_reservations_year": total_reservations_year,
            "approved_reservations_year": approved_reservations_year,
            "pending_reservations_year": pending_reservations_year,
            "rejected_reservations_year": rejected_reservations_year,
            "approved_pct": approved_pct,
            "pending_pct": pending_pct,
            "rejected_pct": rejected_pct,
            "reservations_variation": reservations_variation,
            "approved_variation": approved_variation,
            "prev_reservations_count": prev_reservations_count,
            "prev_reservations_approved": prev_reservations_approved,
            "reservations_by_product": reservations_by_product,
            "reservations_by_category": reservations_by_category,
            "monthly_reservations": monthly_reservations,
            "total_workshops_year": total_workshops_year,
            "total_registered_year": total_registered_year,
            "total_attendees_year": total_attendees_year,
            "attendance_rate_year": attendance_rate_year,
            "workshops_variation": workshops_variation,
            "registered_variation": registered_variation,
            "prev_workshops_count": prev_workshops_count,
            "prev_workshops_registered": prev_workshops_registered,
            "workshops_by_location": workshops_by_location,
            "monthly_workshops": monthly_workshops,
            "most_registered_workshops": most_registered_workshops,
            "best_attendance_workshops": best_attendance_workshops,
            "reservations": reservations_data,
        },
    )


@user_passes_test(is_staff_or_superuser)
def structure_create(request):
    if request.method == "POST":
        form = StructureForm(request.POST, request.FILES)
        if form.is_valid():
            structure = form.save()
            messages.success(
                request, "La structure a \u00e9t\u00e9 cr\u00e9\u00e9e avec succ\u00e8s.")
            return redirect("structure_list")
        structure = None
    else:
        form = StructureForm()
        structure = None
    return render(
        request, "shop/structure_form.html", {"form": form, "structure": structure}
    )


def structure_create_register(request):
    if request.method == "POST":
        form = StructureRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            structure = form.save(commit=False)
            structure.valid = False
            structure.save()
            messages.success(
                request, "Merci pour votre demande d'inscription.")
            return redirect("home")
    else:
        form = StructureRegisterForm()
    return render(request, "shop/structure_form_register.html", {"form": form})


@user_passes_test(is_staff_or_superuser)
def structure_update(request, pk):
    structure = get_object_or_404(Structure, pk=pk)
    if request.method == "POST":
        form = StructureForm(
            request.POST, request.FILES, instance=structure
        )
        if form.is_valid():
            instance = form.save(commit=False)
            instance.save()
            messages.success(
                request, "La structure a \u00e9t\u00e9 modifi\u00e9e avec succ\u00e8s.")
            return redirect("structure_list")
    else:
        form = StructureForm(instance=structure)
    return render(
        request,
        "shop/structure_form.html",
        {"form": form, "structure": structure},
    )


@user_passes_test(is_staff_or_superuser)
def structure_validate(request, pk):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])
    structure = get_object_or_404(Structure, pk=pk)
    structure.is_registered = True
    structure.save()

    from notifications.email_service import send_notification
    send_notification("structure_validated", {
        "structure": structure,
    }, extra_recipients=[structure.email])

    messages.success(request, "La structure a \u00e9t\u00e9 valid\u00e9e avec succ\u00e8s.")
    return redirect("structure_list")


@user_passes_test(is_staff_or_superuser)
def structure_delete(request, pk):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])
    get_object_or_404(Structure, pk=pk).delete()
    return redirect("structure_list")
