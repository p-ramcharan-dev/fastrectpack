"""Benchmark for sizes that are not plain ints (added in 0.2.0): original rectpack vs fastrectpack, interleaved.

    python bench/run_mixed.py            # writes results/mixed.json and results/mixed.md
    python bench/run_mixed.py --quick    # 100 and 300 rectangles only

The first case is the way the gdsfactory package calls rectpack (gdsfactory/pack.py): integer rectangle sizes,
one bin whose size is a numpy.float64, MaxRectsBlsf, best-bin-fit, sort by area, no rotation.
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402
import numpy as np  # noqa: E402
import rectpack  # noqa: E402

import fastrectpack  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true")
ap.add_argument("--cpus", default="0-13", help="logical CPUs to restrict to on Windows; 'all' = no restriction")
ap.add_argument("--out", default="results/mixed")
args = ap.parse_args()

if not (fastrectpack.NATIVE_AVAILABLE and fastrectpack._maxrects._native.MIXED_PATH):
    raise SystemExit("this build of fastrectpack has no native float path")


def workload(kind, n):
    """Returns (rects, bin_width, bin_height). One bin, sized so that everything fits."""
    rng = random.Random(f"mixed/{kind}/{n}")
    sizes = [(rng.randint(10, 200), rng.randint(10, 200)) for _ in range(n)]
    side = np.asarray(np.array([1.0, 1.0]) / np.sqrt(2.0) * np.sqrt(2.2 * sum(w * h for w, h in sizes)), dtype=np.float64)
    if kind == "gdsfactory":      # int rectangles, numpy.float64 bin
        return [(w, h, i) for i, (w, h) in enumerate(sizes)], side[0], side[1]
    if kind == "float":           # Python floats everywhere
        return [(w + 0.25, h + 0.1, i) for i, (w, h) in enumerate(sizes)], float(side[0]), float(side[1])
    if kind == "numpy_int":       # numpy.int64 rectangles (sizes read from an array), int bin
        arr = np.asarray(sizes, dtype=np.int64)
        return [(arr[i, 0], arr[i, 1], i) for i in range(n)], int(side[0]), int(side[1])
    raise ValueError(kind)


def typed(rect_list):
    """rect_list() with the type of every number spelled out, so the digest covers types too."""
    return [tuple((type(v).__name__, v) for v in row) for row in rect_list]


KWARGS = dict(mode=rectpack.PackingMode.Offline, bin_algo=rectpack.PackingBin.BBF, sort_algo=rectpack.SORT_AREA, rotation=False)


if args.cpus == "all":
    pinned = harness.pin(None)
else:
    lo, _, hi = args.cpus.partition("-")
    pinned = harness.pin(range(int(lo), int(hi or lo) + 1))
out = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "env": {**harness.environment(), **pinned, "numpy": np.__version__},
       "config": "Offline, BBF, MaxRectsBlsf, SORT_AREA, rotation=False, one bin",
       "statistic": "speedup = best original time / best fastrectpack time over interleaved rounds",
       "cases": []}
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

for n in ((100, 300) if args.quick else (100, 300, 1000)):
    for kind in ("gdsfactory", "float", "numpy_int"):
        rects, bw, bh = workload(kind, n)
        bins = [(bw, bh, 1)]
        fns = {
            "original": lambda: harness.run_pack(rectpack, rects, bins, pack_algo=rectpack.MaxRectsBlsf, **KWARGS),
            "native": lambda: harness.run_pack(fastrectpack, rects, bins, pack_algo=fastrectpack.MaxRectsBlsf, **KWARGS),
        }
        reps = 7 if n <= 300 else 3
        stats, results = harness.compare(fns, reps=reps, warmup=1 if n <= 300 else 0)
        digests = {k: harness.digest(typed(v)) for k, v in results.items()}
        identical = len(set(digests.values())) == 1
        o, c = stats["original"]["min_s"], stats["native"]["min_s"]
        ratios = [a / b for a, b in zip(stats["original"]["all_s"], stats["native"]["all_s"])]
        out["cases"].append({"kind": kind, "n": n, "reps": reps, "placed": len(results["original"]), "identical_output": identical,
                             "digests": digests, "speedup_best_of": o / c, "speedup_min": min(ratios), "speedup_max": max(ratios),
                             "stats": {k: {"min_s": v["min_s"], "max_s": v["max_s"], "all_s": v["all_s"]} for k, v in stats.items()}})
        print(f"{kind:10s} n={n:5d} identical={identical}  original {o:8.3f}s  native {c:7.4f}s (x{o/c:6.0f})", flush=True)
        harness.dump(args.out + ".json", out)

lines = ["| Input | Rectangles | Original rectpack | fastrectpack (C++) | Speedup | Speedup range across rounds | Output identical, types included |",
         "|---|---|---|---|---|---|---|"]
names = {"gdsfactory": "int rectangles, `numpy.float64` bin (gdsfactory)", "float": "`float` rectangles and bin",
         "numpy_int": "`numpy.int64` rectangles, int bin"}
for c in out["cases"]:
    o, v = c["stats"]["original"]["min_s"], c["stats"]["native"]["min_s"]
    lines.append(f"| {names[c['kind']]} | {c['n']:,} | {o:.3f} s | {v:.4f} s | {o/v:.0f}x | {c['speedup_min']:.0f}x to {c['speedup_max']:.0f}x | {'yes' if c['identical_output'] else 'NO'} |")
with open(args.out + ".md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("saved", args.out + ".json", args.out + ".md")
if not all(c["identical_output"] for c in out["cases"]):
    raise SystemExit(1)
