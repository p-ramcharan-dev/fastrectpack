"""Main benchmark: original rectpack vs pure-Python fixes vs fastrectpack (C++), interleaved, with parity checks.

One command reproduces every number in README.md / BENCHMARKS.md:

    python bench/run_bench.py            # full run, writes results/bench.json and results/bench.md
    python bench/run_bench.py --quick    # small sizes only (about a minute)
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cheap_wins  # noqa: E402
import harness  # noqa: E402
import rectpack  # noqa: E402
import workloads  # noqa: E402

import fastrectpack  # noqa: E402

FULL = [("random", 200), ("random", 500), ("random", 1000), ("random", 2000), ("random", 5000),
        ("cutting", 500), ("cutting", 1000), ("cutting", 2000),
        ("sprites", 500), ("sprites", 1000), ("sprites", 2000),
        ("skewed", 500), ("skewed", 1000), ("skewed", 2000)]
QUICK = [("random", 200), ("random", 500), ("cutting", 500), ("sprites", 500), ("skewed", 500)]

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true")
ap.add_argument("--cpus", default="0-13", help="logical CPUs to restrict to on Windows, e.g. 0-13 (the fast cores on the reference machine); 'all' = no restriction")
ap.add_argument("--out", default="results/bench")
args = ap.parse_args()

if not fastrectpack.NATIVE_AVAILABLE:
    raise SystemExit("fastrectpack's C++ extension is not built; run `pip install .` first")

if args.cpus == "all":
    pinned = harness.pin(None)
else:
    lo, _, hi = args.cpus.partition("-")
    pinned = harness.pin(range(int(lo), int(hi or lo) + 1))
out = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "env": {**harness.environment(), **pinned},
       "config": "newPacker() defaults: Offline, BBF, MaxRectsBssf, SORT_AREA, rotation=True",
       "statistic": "speedup = best original time / best variant time over interleaved rounds", "cases": []}
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

for kind, n in (QUICK if args.quick else FULL):
    rects, bins = workloads.make(kind, n)
    fns = {
        "original": lambda: harness.run_pack(rectpack, rects, bins),
        "python_fixes": lambda: harness.run_pack(rectpack, rects, bins, pack_algo=cheap_wins.Step2Bssf),
        "native": lambda: harness.run_pack(fastrectpack, rects, bins),
    }
    reps = 7 if n <= 1000 else (5 if n <= 2000 else 3)
    stats, results = harness.compare(fns, reps=reps, warmup=1 if n <= 1000 else 0)
    digests = {k: harness.digest(v) for k, v in results.items()}
    identical = len(set(digests.values())) == 1
    res = results["original"]
    row = {"kind": kind, "n": n, "reps": reps, "placed": len(res), "bins_used": max(r[0] for r in res) + 1,
           "identical_output": identical, "digests": digests, "stats": stats}
    out["cases"].append(row)
    o, p, c = (stats[k]["min_s"] for k in ("original", "python_fixes", "native"))
    print(f"{kind:8s} n={n:5d} identical={identical}  original {o:8.3f}s  python_fixes {p:7.3f}s (x{o/p:5.1f})  native {c:7.4f}s (x{o/c:6.1f})", flush=True)
    if not identical:
        print("   !!! OUTPUT DIFFERS", digests, flush=True)
    harness.dump(args.out + ".json", out)

# Markdown table straight from the raw numbers, so docs can be checked against it.
lines = ["| Workload | Rectangles | Bins used | Original rectpack | Pure-Python fixes | fastrectpack (C++) | Speedup, fixes | Speedup, C++ | Output identical |",
         "|---|---|---|---|---|---|---|---|---|"]
for c in out["cases"]:
    o, p, v = (c["stats"][k]["min_s"] for k in ("original", "python_fixes", "native"))
    lines.append(f"| {c['kind']} | {c['n']:,} | {c['bins_used']} | {o:.3f} s | {p:.3f} s | {v:.4f} s | {o/p:.1f}x | {o/v:.1f}x | {'yes' if c['identical_output'] else 'NO'} |")
with open(args.out + ".md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("saved", args.out + ".json", args.out + ".md")
if not all(c["identical_output"] for c in out["cases"]):
    raise SystemExit(1)
