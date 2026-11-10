"""Does fastrectpack's fallback to the original Python code cost anything? (Investigation for 0.2.0.)

The 0.1.0 notes reported that gdsfactory-style input (numpy.float64 bin sizes), which 0.1.0 handed to the
original code, took about 2x as long as plain rectpack: 3.99 s against 1.85 s (300 rectangles) and 106.8 s
against 59.8 s (1,000).

This script measures the fallback path directly. `A` is plain rectpack. `B` is fastrectpack with the C++ core
switched off, which is exactly the code 0.1.0 ran for this input: the subclass wrappers, then the original
methods. It reports

  * the number of Python function calls each makes (cProfile), and
  * wall and CPU time for A and B interleaved, in both orders.

    python research/fallback_slowdown.py [rectangles] [rounds]

Findings are in results/fallback_slowdown.txt.
"""
import cProfile
import pstats
import random
import sys
import time

import numpy as np
import rectpack

import fastrectpack
from fastrectpack import _maxrects

n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 6

_maxrects._native = None  # every fastrectpack object now takes the fallback path from the start


def pack_once(mod):
    rng = random.Random(1)
    rects = [(rng.randint(10, 200), rng.randint(10, 200)) for _ in range(n)]
    side = np.float64(np.sqrt(n * 105 * 105 * 2.2) / np.sqrt(2.0))
    p = mod.newPacker(mode=mod.PackingMode.Offline, pack_algo=mod.MaxRectsBlsf, sort_algo=mod.SORT_AREA,
                      bin_algo=mod.PackingBin.BBF, rotation=False)
    for i, (w, h) in enumerate(rects):
        p.add_rect(width=w, height=h, rid=i)
    p.add_bin(width=side, height=side)
    wall, cpu = time.perf_counter(), time.process_time()
    p.pack()
    assert mod is rectpack or p[0]._native is None
    return time.perf_counter() - wall, time.process_time() - cpu, p.rect_list()


MODS = {"A": rectpack, "B": fastrectpack}
print(f"{n} rectangles, numpy.float64 bin. A = rectpack, B = fastrectpack fallback path (C++ core off)")
same = pack_once(rectpack)[2] == pack_once(fastrectpack)[2]
print("identical output:", same)
for label, mod in MODS.items():
    prof = cProfile.Profile()
    prof.enable()
    pack_once(mod)
    prof.disable()
    print(f"python function calls, {label}: {pstats.Stats(prof).total_calls:,}")
for order in ("AB", "BA"):
    print(f"order {order}:")
    for _ in range(rounds):
        row = []
        for label in order:
            wall, cpu, _ = pack_once(MODS[label])
            row.append(f"{label} {wall:.2f}s (cpu {cpu:.2f}s)")
        print("   " + "   ".join(row), flush=True)
