"""install() / uninstall(): make `rectpack` itself hand out the accelerated classes.

For code you do not control. A library that does `import rectpack` and then calls `rectpack.newPacker(...)`
or names `rectpack.MaxRectsBlsf` cannot be told to import fastrectpack instead, but after `install()` it gets
the accelerated classes anyway.
"""
import inspect
import warnings

import rectpack
from rectpack import maxrects as _maxrects_mod
from rectpack import packer as _packer_mod

from . import _maxrects

_NAMES = ("MaxRectsBl", "MaxRectsBssf", "MaxRectsBaf", "MaxRectsBlsf")

# The original classes, captured before anything is replaced.
_ORIGINAL = {name: getattr(_maxrects_mod, name) for name in _NAMES}
_FAST = {name: getattr(_maxrects, name) for name in _NAMES}

_installed = False


def _functions_with_defaults():
    """Every function in rectpack.packer that may have a MaxRects class as a default argument:
    newPacker and the __init__ of each packer class."""
    for obj in vars(_packer_mod).values():
        if inspect.isfunction(obj):
            yield obj
        elif inspect.isclass(obj) and obj.__module__ == _packer_mod.__name__:
            for member in vars(obj).values():
                if inspect.isfunction(member):
                    yield member


def _swap(old, new):
    by_old = {old[name]: new[name] for name in _NAMES}
    # 1. The names people look up: rectpack.X, rectpack.maxrects.X, and rectpack.packer's own copy.
    for module in (rectpack, _maxrects_mod, _packer_mod):
        for name in _NAMES:
            if getattr(module, name, None) is old[name]:
                setattr(module, name, new[name])
    # 2. Default arguments, which Python fixed when rectpack was imported (newPacker's `pack_algo=MaxRectsBssf`).
    #    Changing them on the function object also reaches code that did `from rectpack import newPacker` earlier.
    for fn in _functions_with_defaults():
        if fn.__defaults__ and any(d in by_old for d in fn.__defaults__ if inspect.isclass(d)):
            fn.__defaults__ = tuple(by_old.get(d, d) if inspect.isclass(d) else d for d in fn.__defaults__)


def install():
    """Make `rectpack` use the accelerated MaxRects classes, for every caller in this process.

    After this, `rectpack.newPacker()`, `rectpack.MaxRectsBssf` and the other three MaxRects names give the
    fastrectpack classes, so libraries that use rectpack internally get faster without being changed. Packings
    are identical to the original's.

    Call it once, before the code you want to speed up runs. A class that some module already imported by name
    (`from rectpack import MaxRectsBssf`, done before this call) keeps pointing at the original; `newPacker`
    is updated either way. Calling it twice is harmless. `uninstall()` reverses it.
    """
    global _installed
    if not _maxrects.NATIVE_AVAILABLE:
        warnings.warn("fastrectpack's C++ extension is not available, so install() will not make rectpack faster",
                      RuntimeWarning, stacklevel=2)
    if not _installed:
        _swap(_ORIGINAL, _FAST)
        _installed = True


def uninstall():
    """Undo install(): `rectpack` hands out its own classes again. Objects that already exist are not changed."""
    global _installed
    if _installed:
        _swap(_FAST, _ORIGINAL)
        _installed = False


def is_installed():
    return _installed
