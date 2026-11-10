"""Does rectpack's value-based duplicate removal actually fire, and does it hurt packings?

Original code (rectpack/maxrects.py):
    contained = set()
    for m1, m2 in itertools.combinations(self._max_rects, 2):
        if m1.contains(m2): contained.add(m2)
        elif m2.contains(m1): contained.add(m1)
    self._max_rects = [m for m in self._max_rects if m not in contained]
Rectangle.__eq__/__hash__ compare by value, so if two free rectangles are IDENTICAL, one lands in `contained`
and then BOTH are filtered out. We count how often that happens and compare against a variant that keeps one copy.
"""
import collections
import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
import rectpack  # noqa: E402
import workloads  # noqa: E402
from rectpack import maxrects  # noqa: E402

stats = collections.Counter()
orig = maxrects.MaxRects._remove_duplicates


def counting(self):
    vals = collections.Counter((m.x, m.y, m.width, m.height) for m in self._max_rects)
    dups = sum(c for c in vals.values() if c > 1)
    stats["calls"] += 1
    if dups:
        stats["calls_with_identical_pair"] += 1
        stats["free_rects_lost_to_pair_rule"] += dups  # all copies get removed, including the 'kept' one
    orig(self)


def keep_one_copy(self):
    """What the code would do if identical rectangles were collapsed to one instead of both removed."""
    contained = set()
    rects = self._max_rects
    seen = {}
    for i, m in enumerate(rects):
        seen.setdefault((m.x, m.y, m.width, m.height), i)
    for (i1, m1), (i2, m2) in itertools.combinations(list(enumerate(rects)), 2):
        a = (m1.x, m1.y, m1.width, m1.height)
        b = (m2.x, m2.y, m2.width, m2.height)
        if a == b:
            contained.add(i2)  # drop the later copy only
        elif m1.contains(m2):
            contained.add(i2)
        elif m2.contains(m1):
            contained.add(i1)
    self._max_rects = [m for i, m in enumerate(rects) if i not in contained]


def pack(kind, n, seed):
    rects, bins = workloads.make(kind, n, seed)
    p = rectpack.newPacker()
    for w, h, rid in rects:
        p.add_rect(w, h, rid)
    for w, h, c in bins:
        p.add_bin(w, h, c)
    p.pack()
    rl = p.rect_list()
    return len(rl), (max(r[0] for r in rl) + 1 if rl else 0)


rows = []
for kind in ("random", "sprites", "cutting", "skewed"):
    for seed in range(1, 7):
        n = 300
        maxrects.MaxRects._remove_duplicates = counting
        stats.clear()
        placed, bins_a = pack(kind, n, seed)
        s = dict(stats)
        maxrects.MaxRects._remove_duplicates = keep_one_copy
        placed2, bins_b = pack(kind, n, seed)
        maxrects.MaxRects._remove_duplicates = orig
        rows.append((kind, seed, s.get("calls", 0), s.get("calls_with_identical_pair", 0), s.get("free_rects_lost_to_pair_rule", 0), placed, bins_a, placed2, bins_b))

print(f"{'workload':9s} seed calls  calls_with_identical_pair  rects_dropped_by_rule   placed/bins(original)   placed/bins(keep-one-copy)")
for r in rows:
    print(f"{r[0]:9s} {r[1]:4d} {r[2]:5d} {r[3]:10d} {r[4]:20d}      {r[5]:4d}/{r[6]:<3d}                {r[7]:4d}/{r[8]:<3d}")
tot_calls = sum(r[2] for r in rows)
tot_hit = sum(r[3] for r in rows)
print(f"\nOverall: identical-pair rule fired in {tot_hit} of {tot_calls} _remove_duplicates calls ({tot_hit / tot_calls * 100:.2f}%).")
diff = [(r[0], r[1], r[6], r[8]) for r in rows if (r[5], r[6]) != (r[7], r[8])]
print(f"Packings whose placed-count or bin-count differs between original and keep-one-copy: {len(diff)} of {len(rows)}")
for d in diff[:10]:
    print("  ", d)
