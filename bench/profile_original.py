"""Where does the time go in the ORIGINAL rectpack? (cProfile adds overhead, so read the shares, not the seconds.)

Usage: python bench/profile_original.py [kind] [n]
"""
import cProfile
import io
import os
import pstats
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402
import rectpack  # noqa: E402
import workloads  # noqa: E402

harness.pin(4)
kind = sys.argv[1] if len(sys.argv) > 1 else "random"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
rects, bins = workloads.make(kind, n)

# Instrument the algorithm to learn the free-rectangle count the loops actually run over.
sizes = []
orig_select = rectpack.maxrects.MaxRects._select_position


def counting_select(self, w, h):
    sizes.append(len(self._max_rects))
    return orig_select(self, w, h)


rectpack.maxrects.MaxRects._select_position = counting_select
pr = cProfile.Profile()
pr.enable()
result = harness.run_pack(rectpack, rects, bins)
pr.disable()
rectpack.maxrects.MaxRects._select_position = orig_select

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("tottime")
ps.print_stats(14)
print(f"workload={kind} n={n} placed={len(result)}")
print(f"_select_position calls: {len(sizes):,}; free rectangles per call: mean {sum(sizes)/len(sizes):.1f}, max {max(sizes)}")
print(s.getvalue()[:5200])

# Share of total time by function family (inclusive time, from cProfile)
total = ps.total_tt
fam = {"_remove_duplicates": 0.0, "_select_position": 0.0, "_split": 0.0, "_rect_fitness": 0.0}
for (fname, line, func), (cc, nc, tt, ct, callers) in ps.stats.items():
    if func in fam and "rectpack" in fname:
        fam[func] = ct
print("inclusive share of profiled time:")
for k, v in fam.items():
    print(f"  {k:20s} {v / total * 100:5.1f}%")
