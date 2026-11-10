"""Native-backed drop-in replacements for rectpack's MaxRects* classes.

Each class subclasses the original (so isinstance checks and every method we do not override still work) and
runs the algorithm in C++ while every size is a Python int, a Python float, a numpy.float64 or a numpy.int64.
Results have the same values and the same types as the original's. It falls back to the original Python code,
permanently for that object, the first time it sees anything else (Decimals, bools, other numpy types, NaN,
infinity, zero or negative sizes, sizes above 2^30). The fallback is the original code, so results and errors
are the same.
"""
from rectpack import maxrects as _orig
from rectpack.geometry import Rectangle
from rectpack.pack_algo import PackingAlgorithm

try:
    from . import _native
except ImportError:  # extension not built: everything below degrades to the original behaviour
    _native = None

NATIVE_AVAILABLE = _native is not None


class _NativeMaxRects:
    _variant = 0  # overridden by each concrete class

    def reset(self):
        PackingAlgorithm.reset(self)  # self.rectangles = []
        self.__dict__.pop("_max_rects", None)
        core = None
        if _native is not None:
            try:
                core = _native.Core(self.width, self.height, bool(self.rot), self._variant)
            except _native.Deopt:
                core = None
        self._native = core
        if core is None:
            self._max_rects = [Rectangle(0, 0, self.width, self.height)]

    def _deopt(self):
        """Hand the current state over to the original Python implementation for good."""
        core = self._native
        self._max_rects = [Rectangle(*t) for t in core.free_rects()]
        self._native = None

    def __getattr__(self, name):
        # Only reached when normal lookup fails: lets code that peeks at _max_rects keep working.
        if name == "_max_rects":
            core = self.__dict__.get("_native")
            if core is not None:
                return [Rectangle(*t) for t in core.free_rects()]
        raise AttributeError(name)

    def fitness(self, width, height):
        core = self._native
        if core is not None:
            try:
                return core.fitness(width, height)
            except _native.Deopt:
                self._deopt()
        return super().fitness(width, height)

    def add_rect(self, width, height, rid=None):
        core = self._native
        if core is not None:
            try:
                placed = core.add_rect(width, height)
            except _native.Deopt:
                self._deopt()
            else:
                if placed is None:
                    return None
                rect = Rectangle(*placed)
                rect.rid = rid
                self.rectangles.append(rect)
                return rect
        return super().add_rect(width, height, rid)

    # pickle / copy.deepcopy: the C++ object cannot be pickled, so serialise as plain Python state
    def __getstate__(self):
        state = dict(self.__dict__)
        core = state.pop("_native", None)
        if core is not None:
            state["_max_rects"] = [Rectangle(*t) for t in core.free_rects()]
        state["_native"] = None
        return state


_BL = _native.BL if _native else 0
_BSSF = _native.BSSF if _native else 1
_BAF = _native.BAF if _native else 2
_BLSF = _native.BLSF if _native else 3


class MaxRectsBl(_NativeMaxRects, _orig.MaxRectsBl):
    _variant = _BL


class MaxRectsBssf(_NativeMaxRects, _orig.MaxRectsBssf):
    """Best Short Side Fit (the rectpack default)."""
    _variant = _BSSF


class MaxRectsBaf(_NativeMaxRects, _orig.MaxRectsBaf):
    _variant = _BAF


class MaxRectsBlsf(_NativeMaxRects, _orig.MaxRectsBlsf):
    _variant = _BLSF
