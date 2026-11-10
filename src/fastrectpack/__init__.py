"""fastrectpack: a drop-in accelerator for rectpack (https://github.com/secnot/rectpack).

Use it exactly like rectpack:

    from fastrectpack import newPacker
    packer = newPacker()
    ...

Everything rectpack exports is re-exported unchanged, except the MaxRects algorithms, which run in C++ when
all sizes are plain Python ints. Any other input is handled by the original rectpack code.
"""
from rectpack import *  # noqa: F401,F403  (re-export the full original API)
from rectpack import SORT_AREA, PackingBin, PackingMode
from rectpack import newPacker as _newPacker

from ._maxrects import NATIVE_AVAILABLE as NATIVE_AVAILABLE
from ._maxrects import MaxRectsBaf as MaxRectsBaf
from ._maxrects import MaxRectsBl as MaxRectsBl
from ._maxrects import MaxRectsBlsf as MaxRectsBlsf
from ._maxrects import MaxRectsBssf as MaxRectsBssf

__version__ = "0.1.0"


def newPacker(mode=PackingMode.Offline, bin_algo=PackingBin.BBF, pack_algo=MaxRectsBssf,
              sort_algo=SORT_AREA, rotation=True):
    """Same signature and behaviour as rectpack.newPacker; the default algorithm is the accelerated one."""
    return _newPacker(mode=mode, bin_algo=bin_algo, pack_algo=pack_algo, sort_algo=sort_algo, rotation=rotation)
