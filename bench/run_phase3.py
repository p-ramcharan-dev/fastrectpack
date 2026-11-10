"""Phase 3 measurement: original vs each cheap pure-Python step, interleaved, with a parity check on every output."""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cheap_wins  # noqa: E402
import harness  # noqa: E402
import rectpack  # noqa: E402
import workloads  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=5)
ap.add_argument("--cpu", type=int, default=-1)
ap.add_argument("--out", default="results/phase3.json")
args = ap.parse_args()
pinned = harness.pin(None if args.cpu < 0 else args.cpu)

CASES = [("random", 500), ("random", 1000), ("skewed", 1000), ("sprites", 1000), ("sprites", 2000), ("cutting", 2000)]
out = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "env": {**harness.environment(), **pinned}, "cases": []}
os.makedirs("results", exist_ok=True)

for kind, n in CASES:
    rects, bins = workloads.make(kind, n)
    fns = {
        "original": lambda: harness.run_pack(rectpack, rects, bins),
        "step1_incremental_dedupe": lambda: harness.run_pack(rectpack, rects, bins, pack_algo=cheap_wins.Step1Bssf),
        "step2_plus_single_fitness": lambda: harness.run_pack(rectpack, rects, bins, pack_algo=cheap_wins.Step2Bssf),
    }
    stats, results = harness.compare(fns, reps=args.reps, warmup=0 if n >= 2000 else 1)
    digests = {k: harness.digest(v) for k, v in results.items()}
    same = len(set(digests.values())) == 1
    row = {"kind": kind, "n": n, "identical_output": same, "digests": digests, "stats": stats}
    out["cases"].append(row)
    line = f"{kind:8s} n={n:5d} identical={same} | "
    for name, s in stats.items():
        sp = s["speedup_vs_original_best_of"]
        line += f"{name.split('_')[0]}: best {s['min_s']:.3f}s (x{sp:.1f}) "
    print(line, flush=True)
    if not same:
        print("   !!! OUTPUT DIFFERS", digests)
    harness.dump("results/phase3.json" if args.out is None else args.out, out)
print("saved", args.out)
