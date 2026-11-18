"""Fuzzy Mamdani-style scoring for kos suitability; no training dataset is required."""


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def trapezoid(value, a, b, c, d):
    x = float(value)
    if x <= a:
        return 1.0 if a == b else 0.0
    if x < b:
        return (x - a) / (b - a)
    if x <= c:
        return 1.0
    if x < d:
        return (d - x) / (d - c)
    return 0.0


def triangle(value, a, b, c):
    return trapezoid(value, a, b, b, c)


def _min(*values):
    return min(values) if values else 0.0


def score_kos(kos, budget_ribu, max_distance_km, min_rating, require_ac=False):
    """Return a suitability score, label, and plain-language criteria notes."""
    price = float(kos.harga)
    distance = float(kos.jarak_km)
    rating = float(kos.rating)
    budget = max(float(budget_ribu), 1.0)
    preferred_distance = max(float(max_distance_km), 0.1)
    desired_rating = max(1.0, min(float(min_rating), 5.0))

    price_ratio = price / budget
    distance_ratio = distance / preferred_distance
    rating_fit = _clamp((rating - desired_rating + 1.0) / (6.0 - desired_rating))

    price_terms = {
        "hemat": trapezoid(price_ratio, 0.0, 0.0, 0.65, 0.95),
        "sesuai": triangle(price_ratio, 0.72, 1.0, 1.28),
        "mahal": trapezoid(price_ratio, 1.02, 1.25, 2.2, 2.2),
    }
    distance_terms = {
        "dekat": trapezoid(distance_ratio, 0.0, 0.0, 0.38, 0.72),
        "sedang": triangle(distance_ratio, 0.45, 0.85, 1.2),
        "jauh": trapezoid(distance_ratio, 1.0, 1.3, 2.5, 2.5),
    }
    rating_terms = {
        "rendah": trapezoid(rating_fit, 0.0, 0.0, 0.2, 0.45),
        "cukup": triangle(rating_fit, 0.3, 0.55, 0.78),
        "tinggi": trapezoid(rating_fit, 0.65, 0.82, 1.0, 1.0),
    }
    ac_fit = 0.1 if require_ac and not kos.ac else 1.0

    rules = [
        (_min(price_terms["hemat"], distance_terms["dekat"], rating_terms["tinggi"], ac_fit), "sangat"),
        (_min(price_terms["hemat"], distance_terms["dekat"], rating_terms["cukup"], ac_fit), "baik"),
        (_min(price_terms["hemat"], distance_terms["sedang"], rating_terms["tinggi"], ac_fit), "baik"),
        (_min(price_terms["sesuai"], distance_terms["dekat"], rating_terms["tinggi"], ac_fit), "baik"),
        (_min(price_terms["hemat"], distance_terms["sedang"], rating_terms["cukup"], ac_fit), "baik"),
        (_min(price_terms["sesuai"], distance_terms["sedang"], rating_terms["tinggi"], ac_fit), "cukup"),
        (_min(price_terms["sesuai"], distance_terms["dekat"], rating_terms["cukup"], ac_fit), "cukup"),
        (_min(price_terms["mahal"], distance_terms["dekat"], rating_terms["tinggi"], ac_fit), "cukup"),
        (_min(price_terms["hemat"], distance_terms["jauh"], rating_terms["tinggi"], ac_fit), "cukup"),
        (_min(price_terms["mahal"], distance_terms["jauh"], rating_terms["rendah"], ac_fit), "rendah"),
        (_min(price_terms["sesuai"], distance_terms["jauh"], rating_terms["rendah"], ac_fit), "rendah"),
    ]

    universe = list(range(101))
    output_sets = {
        "rendah": [trapezoid(x, 0, 0, 25, 48) for x in universe],
        "cukup": [triangle(x, 30, 52, 73) for x in universe],
        "baik": [triangle(x, 58, 77, 92) for x in universe],
        "sangat": [trapezoid(x, 80, 92, 100, 100) for x in universe],
    }
    aggregate = [0.0] * len(universe)
    for strength, output_term in rules:
        if strength <= 0:
            continue
        clipped = [min(strength, membership) for membership in output_sets[output_term]]
        aggregate = [max(current, candidate) for current, candidate in zip(aggregate, clipped)]

    area = sum(aggregate)
    score = sum(x * membership for x, membership in zip(universe, aggregate)) / area if area else 25.0
    score = round(score, 1)
    if score >= 82:
        label = "Sangat cocok"
    elif score >= 65:
        label = "Cocok"
    elif score >= 45:
        label = "Cukup cocok"
    else:
        label = "Kurang sesuai"

    notes = [
        "Harga masuk batas anggaran" if price <= budget else "Harga melewati batas anggaran",
        "Jarak sesuai preferensi" if distance <= preferred_distance else "Jarak melewati preferensi",
        "Rating memenuhi target" if rating >= desired_rating else "Rating di bawah target",
    ]
    if require_ac:
        notes.append("Memiliki AC" if kos.ac else "Tidak memiliki AC yang diminta")
    return {"score": score, "label": label, "notes": notes}
