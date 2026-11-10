"""Phase 3: pure-Python fixes to the ORIGINAL rectpack code path, no C++. Each step must give identical output.

Profile of the original (reproduce with bench/profile_original.py): _remove_duplicates is 88-94% of the time. It re-compares every pair of
free rectangles after each placement, but the list it leaves behind never contains a rectangle that contains
another, so only pairs that involve a newly created piece can change anything.

  Step 1  incremental duplicate removal (only pairs involving new pieces)
  Step 2  step 1 + evaluate the fitness once per candidate in _select_position (the original evaluates it twice)
"""
import operator

import rectpack
from rectpack.geometry import Rectangle

first_item = operator.itemgetter(0)


class _IncrementalDedupe:
    def _split(self, rect):
        out, new_idx = [], []
        for r in self._max_rects:
            if r.intersects(rect):
                for piece in self._generate_splits(r, rect):
                    new_idx.append(len(out))
                    out.append(piece)
            else:
                out.append(r)
        self._max_rects = out
        self._new_idx = new_idx

    def _remove_duplicates(self):
        new_idx = self._new_idx
        if not new_idx:
            return
        rects = self._max_rects
        n = len(rects)
        flagged = set()  # by value, like the original: equal rectangles are removed together
        for i in new_idx:
            a = rects[i]
            for j in range(n):
                if j != i:
                    b = rects[j]
                    if a.contains(b):
                        flagged.add(b)
                    if b.contains(a):
                        flagged.add(a)
        if flagged:
            self._max_rects = [m for m in rects if m not in flagged]


class _SingleFitness:
    """MaxRects._select_position, evaluating _rect_fitness once per candidate instead of twice."""

    def _select_position(self, w, h):
        if not self._max_rects:
            return None, None
        rf = self._rect_fitness
        best = None
        bkey = None
        for m in self._max_rects:
            f = rf(m, w, h)
            if f is not None and (best is None or f < bkey):
                best, bkey = (w, h, m), f
        if self.rot:
            for m in self._max_rects:
                f = rf(m, h, w)
                if f is not None and (best is None or f < bkey):
                    best, bkey = (h, w, m), f
        if best is None:
            return None, None
        w2, h2, m = best
        return Rectangle(m.x, m.y, w2, h2), m


class Step1Bssf(_IncrementalDedupe, rectpack.MaxRectsBssf):
    pass


class Step2Bssf(_SingleFitness, _IncrementalDedupe, rectpack.MaxRectsBssf):
    pass
