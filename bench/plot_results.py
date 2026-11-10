"""Draw the README benchmark chart (light and dark) from results/summary.md.

    pip install matplotlib        # only needed for this script, not for fastrectpack
    python tools/summarize.py     # regenerates results/summary.md from the raw results
    python bench/plot_results.py  # writes docs/benchmarks-light.png and docs/benchmarks-dark.png

Form: a dumbbell on a log axis. Each row is one workload; the light dot is the pure-Python fix, the dark dot is
the C++ port, both as a speedup over the original rectpack (1x = no change). Colours are two steps of one blue ramp,
validated for each surface with the dataviz palette validator. The same numbers are in the tables in README.md and
BENCHMARKS.md, so no value is available only through the chart.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
                  fixes="#86b6ef", cpp="#1c5cab"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
                 fixes="#184f95", cpp="#6da7ec"),
}
KIND_ORDER = ["random", "skewed", "sprites", "cutting"]
KIND_NOTE = {"cutting": "many bins"}


def read_rows():
    rows = []
    for line in open(os.path.join(ROOT, "results", "summary.md"), encoding="utf-8"):
        if not line.startswith("| ") or line.startswith("| Workload") or line.startswith("|---"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 10 or c[0] not in KIND_ORDER:
            continue
        rows.append(dict(kind=c[0], n=int(c[1].replace(",", "")), fixes=float(c[6].rstrip("x")),
                         cpp=float(c[7].rstrip("x")), identical=c[9] == "yes"))
    return rows


def draw(rows, theme, path):
    t = THEMES[theme]
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]
    fig = plt.figure(figsize=(8.4, 6.4), dpi=144, facecolor=t["surface"])
    ax = fig.add_axes([0.17, 0.11, 0.78, 0.69], facecolor=t["surface"])

    ordered = [r for k in KIND_ORDER for r in sorted((x for x in rows if x["kind"] == k), key=lambda x: x["n"])]
    ys, labels, y = [], [], 0.0
    prev = None
    for r in ordered:
        if prev is not None and r["kind"] != prev:
            y -= 0.7  # gap between workload groups
        ys.append(y)
        labels.append(f"{r['kind']}  {r['n']:,}")
        prev, y = r["kind"], y - 1.0

    ax.set_xscale("log")
    ax.set_xlim(0.8, 450)
    ax.set_ylim(min(ys) - 0.7, max(ys) + 0.7)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200])
    ax.set_xticklabels(["1×", "2×", "5×", "10×", "20×", "50×", "100×", "200×"])
    ax.minorticks_off()
    ax.grid(axis="x", color=t["grid"], linewidth=0.5, zorder=0)
    ax.axvline(1, color=t["axis"], linewidth=1.0, zorder=1)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.tick_params(axis="x", colors=t["muted"], labelsize=9, length=0, pad=6)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, color=t["ink2"], fontsize=9)
    ax.tick_params(axis="y", length=0, pad=8)

    for r, yy in zip(ordered, ys):
        ax.plot([r["fixes"], r["cpp"]], [yy, yy], color=t["muted"], linewidth=1.0, alpha=0.55, zorder=2, solid_capstyle="butt")
        ax.scatter([r["fixes"]], [yy], s=62, color=t["fixes"], edgecolor=t["surface"], linewidth=1.0, zorder=3)
        ax.scatter([r["cpp"]], [yy], s=62, color=t["cpp"], edgecolor=t["surface"], linewidth=1.0, zorder=3)

    # Selective direct labels: the best and the weakest C++ result (everything else is in the tables)
    best = max(zip(ordered, ys), key=lambda p: p[0]["cpp"])
    worst = min(zip(ordered, ys), key=lambda p: p[0]["cpp"])
    for (r, yy), txt in ((best, f"{best[0]['cpp']:.0f}×"), (worst, f"{worst[0]['cpp']:.0f}×")):
        ax.annotate(txt, (r["cpp"], yy), xytext=(9, 0), textcoords="offset points", va="center", ha="left",
                    color=t["ink"], fontsize=9.5, fontweight="bold")
    ax.annotate("many bins: the bin-selection loop is still Python", (worst[0]["cpp"], worst[1]),
                xytext=(34, 0), textcoords="offset points", va="center", ha="left", color=t["ink2"], fontsize=8.5)

    fig.text(0.035, 0.945, "Speedup over the original rectpack", color=t["ink"], fontsize=14, fontweight="bold", ha="left")
    fig.text(0.035, 0.905, f"{len(rows)} workloads, log scale, 1× = no change. Output identical to the original in every case.",
             color=t["ink2"], fontsize=9.5, ha="left")
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=8, markerfacecolor=t["fixes"], markeredgecolor=t["surface"]),
               Line2D([0], [0], marker="o", linestyle="", markersize=8, markerfacecolor=t["cpp"], markeredgecolor=t["surface"])]
    leg = fig.legend(handles, ["Pure-Python fixes (no compiler)", "fastrectpack (C++)"], loc="upper left", bbox_to_anchor=(0.03, 0.885),
                     ncol=2, frameon=False, fontsize=9.5, handletextpad=0.4, columnspacing=1.6)
    for text in leg.get_texts():
        text.set_color(t["ink"])
    fig.text(0.035, 0.025, "Best of interleaved runs on one Windows laptop. Data: results/summary.md (tables in README.md and BENCHMARKS.md).",
             color=t["muted"], fontsize=8, ha="left")
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)


if __name__ == "__main__":
    rows = read_rows()
    assert len(rows) == 14, f"expected 14 workloads in results/summary.md, found {len(rows)}"
    assert all(r["identical"] for r in rows), "a workload is not marked identical; refusing to draw the chart"
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    for theme in THEMES:
        out = os.path.join(ROOT, "docs", f"benchmarks-{theme}.png")
        draw(rows, theme, out)
        print("wrote", out)
