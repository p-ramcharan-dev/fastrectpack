"""Fuzz for the identical-free-rectangle case in rectpack's _remove_duplicates, using tiny sizes on purpose."""
import collections
import random

import rectpack
from rectpack import maxrects

hits = collections.Counter()
examples = []
orig = maxrects.MaxRects._remove_duplicates

def watch(self):
    vals = collections.Counter((m.x, m.y, m.width, m.height) for m in self._max_rects)
    if any(c > 1 for c in vals.values()):
        hits["calls_with_identical_pair"] += 1
        if len(examples) < 3:
            examples.append(([(m.x, m.y, m.width, m.height) for m in self._max_rects], [r[1:] for r in self.rect_list()]))
    hits["calls"] += 1
    orig(self)

maxrects.MaxRects._remove_duplicates = watch
rng = random.Random(2026)
runs = 0
for algo in (rectpack.MaxRectsBl, rectpack.MaxRectsBssf, rectpack.MaxRectsBaf, rectpack.MaxRectsBlsf):
    for _ in range(4000):
        W, H = rng.randint(2, 14), rng.randint(2, 14)
        a = algo(W, H, rot=rng.random() < 0.5)
        runs += 1
        for i in range(rng.randint(1, 25)):
            a.add_rect(rng.randint(1, 6), rng.randint(1, 6), i)
print("runs:", runs, dict(hits))
for ex in examples:
    print("example free list before removal:", ex[0], "| placed so far:", ex[1])
