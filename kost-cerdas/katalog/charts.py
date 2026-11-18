import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = "DejaVu Sans"
from matplotlib.figure import Figure


INK = "#18352d"
GREEN = "#4d8d70"
GOLD = "#d4a858"
GRID = "#e8ece8"


def _as_data_uri(figure):
    output = BytesIO()
    figure.savefig(output, format="png", dpi=140, bbox_inches="tight", facecolor="#ffffff")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    figure.clear()
    return f"data:image/png;base64,{encoded}"


def price_distance_chart(rows):
    figure = Figure(figsize=(7.2, 3.5), layout="constrained")
    axis = figure.subplots()
    distances = [float(row.jarak_km) for row in rows]
    prices = [float(row.harga) for row in rows]
    colors = [GREEN if row.ac else GOLD for row in rows]
    axis.scatter(distances, prices, c=colors, s=60, alpha=0.85, edgecolors="white", linewidths=0.7)
    axis.set_title("Harga dan jarak kos", loc="left", color=INK, fontsize=13, fontweight="bold", pad=12)
    axis.set_xlabel("Jarak dari kampus (km)")
    axis.set_ylabel("Harga (ribu rupiah / bulan)")
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(GRID)
    return _as_data_uri(figure)


def average_price_by_ac_chart(rows):
    figure = Figure(figsize=(7.2, 3.5), layout="constrained")
    axis = figure.subplots()
    categories = [("Tanpa AC", [row for row in rows if not row.ac]), ("Dengan AC", [row for row in rows if row.ac])]
    labels = [label for label, members in categories if members]
    means = [sum(float(row.harga) for row in members) / len(members) for _, members in categories if members]
    counts = [len(members) for _, members in categories if members]
    bars = axis.bar(labels, means, color=[GOLD, GREEN][:len(labels)], width=0.52, zorder=3)
    axis.set_title("Rata-rata harga menurut fasilitas", loc="left", color=INK, fontsize=13, fontweight="bold", pad=12)
    axis.set_ylabel("Harga rata-rata (ribu rupiah / bulan)")
    axis.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(GRID)
    for bar, mean, count in zip(bars, means, counts):
        axis.annotate(
            f"{mean:,.0f} · {count} kos".replace(",", "."),
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 7), textcoords="offset points", ha="center", color=INK, fontsize=9,
        )
    return _as_data_uri(figure)
