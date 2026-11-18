import os
import statistics

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .charts import average_price_by_ac_chart, price_distance_chart
from .fuzzy import score_kos
from .models import Kos
from .services import GeminiUnavailable, explain_dashboard


def _safe_float(value, default, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed))


def _dashboard_summary(rows):
    if not rows:
        return "Belum ada baris data kos di database."
    prices = [float(row.harga) for row in rows]
    distances = [float(row.jarak_km) for row in rows]
    ratings = [float(row.rating) for row in rows]
    ac_rows = [row for row in rows if row.ac]
    no_ac_rows = [row for row in rows if not row.ac]
    ac_summary = (
        f"Rata-rata harga dengan AC: {statistics.mean(float(row.harga) for row in ac_rows):.1f} ribu "
        f"({len(ac_rows)} data). " if ac_rows else "Tidak ada data kos ber-AC. "
    )
    no_ac_summary = (
        f"Rata-rata harga tanpa AC: {statistics.mean(float(row.harga) for row in no_ac_rows):.1f} ribu "
        f"({len(no_ac_rows)} data). " if no_ac_rows else "Tidak ada data kos tanpa AC. "
    )
    return (
        f"Jumlah kos: {len(rows)}. Rentang harga: {min(prices):.0f}–{max(prices):.0f} ribu rupiah/bulan. "
        f"Rata-rata harga: {statistics.mean(prices):.1f} ribu. "
        + ac_summary + no_ac_summary
        + f"Rata-rata jarak: {statistics.mean(distances):.2f} km. "
        + f"Rata-rata rating: {statistics.mean(ratings):.2f}."
    )


def dashboard(request):
    rows = list(Kos.objects.all())
    prices = [float(row.harga) for row in rows]
    distances = [float(row.jarak_km) for row in rows]
    ratings = [float(row.rating) for row in rows]
    summary = _dashboard_summary(rows)
    ai_explanation = None
    ai_error = None

    if request.method == "POST" and request.POST.get("action") == "explain":
        try:
            ai_explanation = explain_dashboard(summary)
        except GeminiUnavailable as exc:
            ai_error = str(exc)

    context = {
        "kos_count": len(rows),
        "average_price": statistics.mean(prices) if prices else 0,
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "average_distance": statistics.mean(distances) if distances else 0,
        "average_rating": statistics.mean(ratings) if ratings else 0,
        "ac_count": sum(1 for row in rows if row.ac),
        "price_distance_chart": price_distance_chart(rows) if rows else None,
        "price_ac_chart": average_price_by_ac_chart(rows) if rows else None,
        "ai_enabled": bool(os.getenv("GEMINI_API_KEY")),
        "ai_explanation": ai_explanation,
        "ai_error": ai_error,
        "data_source": "SkyWee07/Sistem-Cerdas · kos_madiun.csv",
        "sample_kos": rows[:5],
    }
    return render(request, "katalog/dashboard.html", context)


@require_GET
def kos_list(request):
    records = Kos.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        records = records.filter(Q(nama__icontains=query))

    ac_filter = request.GET.get("ac", "")
    if ac_filter == "ya":
        records = records.filter(ac=True)
    elif ac_filter == "tidak":
        records = records.filter(ac=False)

    max_price = request.GET.get("maks_harga", "").strip()
    if max_price:
        try:
            records = records.filter(harga__lte=float(max_price))
        except ValueError:
            max_price = ""

    ordering = request.GET.get("urut", "nama")
    if ordering not in {"nama", "harga", "-harga", "jarak_km", "-jarak_km", "-rating"}:
        ordering = "nama"
    records = records.order_by(ordering)
    return render(request, "katalog/kos_list.html", {
        "kos_list": records,
        "query": query,
        "ac_filter": ac_filter,
        "max_price": max_price,
        "ordering": ordering,
        "result_count": records.count(),
    })


@require_GET
def kos_detail(request, pk):
    kos = get_object_or_404(Kos, pk=pk)
    return render(request, "katalog/kos_detail.html", {"kos": kos})


@require_GET
def recommendations(request):
    budget = _safe_float(request.GET.get("budget"), 1100.0, 100.0, 10000.0)
    max_distance = _safe_float(request.GET.get("jarak"), 2.5, 0.1, 20.0)
    min_rating = _safe_float(request.GET.get("rating"), 3.8, 1.0, 5.0)
    require_ac = request.GET.get("ac") == "ya"

    ranked = []
    for kos in Kos.objects.all():
        result = score_kos(kos, budget, max_distance, min_rating, require_ac)
        ranked.append({"kos": kos, **result})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return render(request, "katalog/recommendations.html", {
        "ranked_kos": ranked,
        "budget": budget,
        "max_distance": max_distance,
        "min_rating": min_rating,
        "require_ac": require_ac,
    })
