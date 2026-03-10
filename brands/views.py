from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import BrandEntry


def home(request):
    return render(request, "brands/home.html")


def live_search(request):
    query = request.GET.get("q", "").strip()
    results = BrandEntry.objects.none()

    if query:
        results = BrandEntry.objects.filter(brand__icontains=query).order_by("brand")[:10]

    context = {
        "query": query,
        "results": results,
    }
    return render(request, "brands/partials/brand_options.html", context)


def selected_brand(request):
    query = request.GET.get("q", "").strip()
    brand = None

    if query:
        brand = BrandEntry.objects.filter(brand__iexact=query).first()

    return render(request, "brands/partials/selection_panel.html", {"brand": brand})


def brand_detail(request, pk):
    brand = get_object_or_404(BrandEntry, pk=pk)
    return render(request, "brands/partials/brand_detail.html", {"brand": brand})


def healthz(request):
    return HttpResponse("ok", content_type="text/plain")
