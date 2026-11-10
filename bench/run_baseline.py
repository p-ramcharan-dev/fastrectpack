"""Baseline: time the ORIGINAL rectpack on every workload and size, and save golden output digests.

Usage:  python bench/run_baseline.py [--quick] [--out results/baseline.json]
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402
import rectpack  # noqa: E402
import workloads  # noqa: E402

# (kind, n) cases. Larger sizes get fewer repetitions because the original is very slow there.
FULL = [("random", 200, 5), ("random", 500, 5), ("random", 1000, 3), ("random", 2000, 3), ("random", 5000, 3),
        ("cutting", 500, 3), ("cutting", 1000, 3), ("cutting", 2000, 3),
        ("sprites", 500, 3), ("sprites", 1000, 3), ("sprites", 2000, 3),
        ("skewed", 500, 3), ("skewed", 1000, 3), ("skewed", 2000, 3)]
QUICK = [("random", 200, 3), ("random", 500, 3), ("cutting", 500, 3)]

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true")
ap.add_argument("--out", default="results/baseline.json")
ap.add_argument("--cpu", type=int, default=4, help="logical CPU to pin to (Windows); -1 = do not pin")
args = ap.parse_args()

pinned = harness.pin(None if args.cpu < 0 else args.cpu)
cases = QUICK if args.quick else FULL
out = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "env": {**harness.environment(), **pinned}, "config": "newPacker() defaults: Offline, BBF, MaxRectsBssf, SORT_AREA, rotation=True", "cases": []}
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

for kind, n, reps in cases:
    rects, bins = workloads.make(kind, n)
    stats, result = harness.measure(lambda: harness.run_pack(rectpack, rects, bins), reps=reps, warmup=1 if n <= 1000 else 0)
    bins_used = (max(r[0] for r in result) + 1) if result else 0
    row = {"kind": kind, "n": n, "placed": len(result), "bins_used": bins_used, "digest": harness.digest(result), **stats}
    out["cases"].append(row)
    print(f"{kind:8s} n={n:5d}  median {stats['median_s']:8.3f}s  min {stats['min_s']:8.3f}  max {stats['max_s']:8.3f}  placed={len(result)} bins={bins_used} digest={row['digest']}", flush=True)
    harness.dump(args.out, out)

print("saved", args.out)
