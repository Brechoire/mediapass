from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.utils import is_staff_or_superuser
from ..forms import CategoryForm
from ..models import Category, Product, Reservation


@user_passes_test(is_staff_or_superuser)
def category_list(request):
    q = request.GET.get("q", "")
    categorys = Category.objects.annotate(
        product_count=Count("products"),
        active_reservations=Count(
            "products__reservations",
            filter=Q(
                products__reservations__is_approved=True,
                products__reservations__end_date__gte=timezone.now(),
            ),
            distinct=True,
        ),
    )
    if q:
        categorys = categorys.filter(name__icontains=q)
    categorys = categorys.order_by("name")
    return render(
        request,
        "shop/category_list.html",
        {"categorys": categorys, "q": q},
    )


def category_detail(request, pk):
    today = timezone.now()

    category = Category.objects.annotate(
        total_active_reservations=Coalesce(
            Sum(
                "products__reservations__quantity",
                filter=Q(
                    products__reservations__is_approved=True,
                    products__reservations__end_date__gte=today,
                ),
            ),
            0,
        )
    ).first()
    if not category:
        raise Http404("Cat\u00e9gorie introuvable")

    reserved_qty_subq = (
        Reservation.objects.filter(
            product=OuterRef("pk"),
            is_approved=True,
            end_date__gte=today,
        )
        .values("product")
        .annotate(total_qty=Sum("quantity"))
        .values("total_qty")
    )

    products = category.products.annotate(
        active_reserved_qty=Coalesce(Subquery(reserved_qty_subq), Value(0)),
        next_return_date=Subquery(
            Reservation.objects.filter(
                product=OuterRef("pk"),
                is_approved=True,
                end_date__gte=today,
            )
            .order_by("-end_date")
            .values("end_date")[:1]
        ),
    )

    return render(
        request,
        "shop/category_detail.html",
        {
            "category": category,
            "products": products,
        },
    )


@user_passes_test(is_staff_or_superuser)
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "La cat\u00e9gorie a \u00e9t\u00e9 cr\u00e9\u00e9e avec succ\u00e8s.")
            return redirect("category_list")
    else:
        form = CategoryForm()
    return render(request, "shop/category_form.html", {"form": form})


@user_passes_test(is_staff_or_superuser)
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect("category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "shop/category_form.html", {"form": form})


@user_passes_test(is_staff_or_superuser)
def category_delete(request, pk):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])
    get_object_or_404(Category, pk=pk).delete()
    return redirect("category_list")
