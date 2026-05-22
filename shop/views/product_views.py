from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.utils import is_staff_or_superuser
from ..forms import ProductForm, ReservationForm
from ..models import Category, Product, Reservation


@user_passes_test(is_staff_or_superuser)
def product_list(request):
    q = request.GET.get("q", "")
    cat = request.GET.get("cat", "")
    sort = request.GET.get("sort", "name")
    dir = request.GET.get("dir", "asc")

    sort_map = {"name": "name", "price": "price", "quantity": "quantity", "status": "status", "category": "category__name"}
    sort_field = sort_map.get(sort, "name")
    if dir == "desc":
        sort_field = f"-{sort_field}"

    products = Product.objects.select_related("category").all()
    if q:
        products = products.filter(name__icontains=q)
    if cat:
        products = products.filter(category_id=cat)
    products = products.order_by(sort_field)

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    categories = Category.objects.all()

    return render(
        request,
        "shop/product_list.html",
        {
            "products": page_obj,
            "page_obj": page_obj,
            "categories": categories,
            "q": q,
            "cat": cat,
            "sort": sort,
            "dir": dir,
        },
    )


@user_passes_test(is_staff_or_superuser)
def product_list_export(request):
    import csv
    from django.http import HttpResponse

    products = Product.objects.select_related("category").all().order_by("name")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="produits.csv"'

    writer = csv.writer(response)
    writer.writerow(["ID", "Nom", "Prix", "Quantit\u00e9", "Disponible", "Cat\u00e9gorie"])
    for p in products:
        writer.writerow([p.pk, p.name, p.price, p.quantity, "Oui" if p.status else "Non", p.category.name])
    return response


def product_list_user(request):
    products = Product.objects.select_related("category").all()
    product_count = products.count()
    return render(
        request,
        "shop/product_list_user.html",
        {"products": products, "product_count": product_count},
    )


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category"), pk=pk
    )
    reservations = Reservation.objects.filter(product=product).select_related(
        "structure"
    )

    if request.method == "POST":
        form = ReservationForm(request.POST, product=product)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.product = product

            new_start = datetime.combine(
                reservation.start_date
                if isinstance(reservation.start_date, date)
                else reservation.start_date.date(),
                reservation.deposit_time,
            )
            new_end = datetime.combine(
                reservation.end_date
                if isinstance(reservation.end_date, date)
                else reservation.end_date.date(),
                reservation.pickup_time,
            )

            existing_reservations = [
                r for r in reservations if r.is_approved
            ]
            has_conflict = any(
                datetime.combine(
                    r.start_date.date()
                    if isinstance(r.start_date, datetime)
                    else r.start_date,
                    r.deposit_time,
                )
                < new_end
                and datetime.combine(
                    r.end_date.date()
                    if isinstance(r.end_date, datetime)
                    else r.end_date,
                    r.pickup_time,
                )
                > new_start
                for r in existing_reservations
            )

            if reservation.start_date == reservation.end_date and reservation.pickup_time <= reservation.deposit_time:
                form.add_error(
                    "pickup_time",
                    "L'heure de fin doit \u00eatre post\u00e9rieure \u00e0 "
                    "l'heure de d\u00e9but si la r\u00e9servation commence et se "
                    "termine le m\u00eame jour.",
                )
            elif has_conflict:
                form.add_error(
                    None,
                    "Le produit est d\u00e9j\u00e0 r\u00e9serv\u00e9 pour ces dates.",
                )
            else:
                reservation.save()
                messages.success(
                    request,
                    "La demande de r\u00e9servation a bien \u00e9t\u00e9 enregistr\u00e9e.",
                )

                if reservation.structure.name != "Mediapass":
                    from notifications.email_service import send_notification
                    send_notification("new_reservation", {
                        "product": product,
                        "reservation": reservation,
                    })

                form = ReservationForm(product=product)
    else:
        form = ReservationForm(product=product)

    return render(
        request,
        "shop/product_detail.html",
        {
            "product": product,
            "form": form,
            "reservations": reservations,
            "upcoming_reservations": reservations.filter(
                is_approved=True, end_date__gte=timezone.now()
            ).order_by("start_date", "deposit_time"),
        },
    )


@user_passes_test(is_staff_or_superuser)
def product_create(request):
    categories = Category.objects.all()
    categories_count = categories.count()
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Le produit a \u00e9t\u00e9 cr\u00e9\u00e9 avec succ\u00e8s.")
            return redirect("product_list")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProductForm()
    return render(
        request,
        "shop/product_form.html",
        {"form": form, "categories_count": categories_count},
    )


@user_passes_test(is_staff_or_superuser)
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Le produit a \u00e9t\u00e9 mis \u00e0 jour avec succ\u00e8s.")
            return redirect("product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "shop/product_form.html", {"form": form})


@user_passes_test(is_staff_or_superuser)
def product_delete(request, pk):
    from django.views.decorators.http import require_POST

    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])
    get_object_or_404(Product, pk=pk).delete()
    messages.success(request, "Le produit a \u00e9t\u00e9 supprim\u00e9 avec succ\u00e8s.")
    return redirect("product_list")
